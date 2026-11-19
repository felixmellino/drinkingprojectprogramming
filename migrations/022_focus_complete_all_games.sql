-- Requires 021_focus_three_stage_flow.sql. Apply after other Focus migrations.
-- New attempts play every task: 0/1 pass = no reward, 2 = x1.25, 3 = x1.5.
-- Running attempts keep their saved configuration; historical awards stay fixed.
begin;
alter table public.focus_attempts add column if not exists stage_results jsonb not null default '{}';
alter table public.focus_attempts add column if not exists boost_multiplier numeric not null default 1.5;
alter table public.drink_entries add column if not exists focus_multiplier numeric;
update public.drink_entries set focus_multiplier=case when focus_attempt_id is null then 1 else 1.5 end
 where focus_multiplier is null;
alter table public.drink_entries alter column focus_multiplier set default 1;
alter table public.drink_entries alter column focus_multiplier set not null;
do $$ begin
 if not exists(select 1 from pg_constraint where conname='focus_entry_multiplier_valid' and conrelid='public.drink_entries'::regclass) then
  alter table public.drink_entries add constraint focus_entry_multiplier_valid check(focus_multiplier in(1,1.25,1.5));
 end if;
 -- Keep the exact previously deployed action for attempts with an older snapshot.
 if to_regprocedure('public._focus_attempt_action_v2(uuid,uuid,integer,text,jsonb)') is null then
  alter function public.focus_attempt_action(uuid,uuid,integer,text,jsonb) rename to _focus_attempt_action_v2;
 end if;
end $$;

create or replace function public._focus_rules(s public.seasons)
returns jsonb language sql immutable set search_path=public as $$
 select case when s.scoring_version='v1' and s.scoring_rules->'focus_challenge'->>'version'='1'
  then s.scoring_rules->'focus_challenge'
  when public._focus_is_test(s) then '{"version":1,"first_unlock":5,"retry_step":2,"memory_length":7,"memory_cells":9,"memory_flash_ms":650,"memory_gap_ms":200,"memory_input_ms":15000,"precision_targets":12,"precision_ms":12000,"ready_seconds":30,"attempt_seconds":180,"delivery_grace_ms":2000,"boost_seconds":3600,"multiplier":1.5}'::jsonb else null end
 || '{"reaction_trials":1,"reaction_median_ms":220,"reaction_response_ms":500,"reaction_wait_min_ms":3500,"reaction_wait_max_ms":6500,"flow_version":3,"reward_multipliers":[1,1,1.25,1.5]}'::jsonb
$$;

create or replace function public._focus_public(a public.focus_attempts,at_time timestamptz)
returns jsonb language sql stable set search_path=public as $$
 select jsonb_build_object('id',a.id,'status',a.status,'phase',a.phase,'step',a.step,'revision',a.revision,
 'started_at',a.started_at,'expires_at',a.expires_at,'signal_at',a.signal_at,'deadline',a.deadline,
 'reaction_ms',a.reaction_ms,'precision_taps',a.precision_taps,'reason',a.reason,
 'boost_ends_at',a.boost_ends_at,'boost_multiplier',a.boost_multiplier,
 'stage_results',a.stage_results,'server_now',at_time,'test_mode',a.test_mode,'config',a.config)
 || case when a.status='running' and a.phase='memory' and at_time<a.signal_at
    then jsonb_build_object('memory',a.challenge->'memory') else '{}'::jsonb end
 || case when a.status='running' and a.phase='precision'
    then jsonb_build_object('positions',a.challenge->'positions') else '{}'::jsonb end
$$;

-- Internal transition: called only after the action/expiry checks under the lobby lock.
create or replace function public._focus_finish_stage(target uuid,success boolean,why text,at_time timestamptz)
returns void language plpgsql set search_path=public as $$
declare a public.focus_attempts%rowtype; s public.seasons%rowtype; stage text; results jsonb;
 wins integer; multiplier numeric;
begin
 select * into a from public.focus_attempts where id=target for update;
 if a.status<>'running' then return; end if;
 stage:=split_part(a.phase,'_',1);
 if stage not in('reaction','memory','precision') or a.stage_results ? stage then raise exception 'focus_invalid_action'; end if;
 results:=a.stage_results||jsonb_build_object(stage,success);
 if stage<>'precision' then
  update public.focus_attempts set stage_results=results,
   phase=case when stage='reaction' then 'memory_ready' else 'precision_ready' end,
   step=0,signal_at=null,deadline=least(at_time+make_interval(secs=>(a.config->>'ready_seconds')::integer),expires_at),
   reason=case when success then null else why end,revision=revision+1 where id=a.id;
 else
  if not(results ? 'reaction' and results ? 'memory') then raise exception 'focus_invalid_action'; end if;
  select count(*) into wins from jsonb_each(results) r where r.value='true'::jsonb;
  multiplier:=case when wins=3 then 1.5 when wins=2 then 1.25 else 1 end;
  select * into s from public.seasons where id=a.season_id;
  update public.focus_attempts set stage_results=results,boost_multiplier=multiplier,
   status=case when multiplier>1 then 'passed' else 'failed' end,completed_at=at_time,
   reason=case when multiplier>1 then null else 'not_enough_passes' end,
   boost_ends_at=case when multiplier>1 then least(at_time+make_interval(secs=>(a.config->>'boost_seconds')::integer),public._focus_window_end(s,at_time)) else null end,
   revision=revision+1 where id=a.id;
 end if;
end $$;

create or replace function public._focus_expire(mid uuid,sid uuid,at_time timestamptz) returns void
language plpgsql set search_path=public as $$
declare a public.focus_attempts%rowtype;
begin
 for a in select * from public.focus_attempts where membership_id=mid and season_id=sid and status='running' loop
  if at_time>=a.expires_at or (a.config->>'flow_version' is distinct from '3' and at_time>a.deadline+interval '2 seconds') then
   update public.focus_attempts set status='failed',reason='timeout',completed_at=at_time,revision=revision+1 where id=a.id;
  elsif at_time>a.deadline+interval '2 seconds' then
   perform public._focus_finish_stage(a.id,false,'timeout',at_time);
  end if;
 end loop;
end $$;

create or replace function public.focus_attempt_action(actor_player uuid,target_attempt uuid,expected_revision integer,
 selected_action text,evidence jsonb) returns jsonb language plpgsql set search_path=public as $$
declare a public.focus_attempts%rowtype; s public.seasons%rowtype; cfg jsonb;
 at_time timestamptz:=statement_timestamp(); ms integer; cell integer; taps jsonb;
 i integer; previous_ms integer:=-1; complete boolean;
begin
 select * into a from public.focus_attempts where id=target_attempt;
 if not found then raise exception 'permission_denied'; end if;
 s:=public._focus_season(actor_player,a.season_id);
 perform pg_advisory_xact_lock(hashtext(s.lobby_id::text));
 if not exists(select 1 from public.lobby_memberships where id=a.membership_id and player_id=actor_player and lobby_id=s.lobby_id)
  then raise exception 'permission_denied'; end if;
 if a.config->>'flow_version' is distinct from '3' then
  return public._focus_attempt_action_v2(actor_player,target_attempt,expected_revision,selected_action,evidence);
 end if;
 perform public._focus_expire(a.membership_id,s.id,at_time);
 select * into a from public.focus_attempts where id=target_attempt;
 if a.status<>'running' or expected_revision<a.revision then return public._focus_public(a,at_time); end if;
 if expected_revision is distinct from a.revision or jsonb_typeof(evidence) is distinct from 'object'
  or octet_length(evidence::text)>8000 then raise exception 'focus_invalid_action'; end if;
 cfg:=a.config;
 if selected_action='fail' then
  -- A client may concede its current task, never choose a success or a reward.
  perform public._focus_finish_stage(a.id,false,'miss',at_time);
 elsif selected_action='ready' and a.phase in('reaction_ready','memory_ready','precision_ready') then
  if a.phase='reaction_ready' then
   update public.focus_attempts set phase='reaction',signal_at=at_time+make_interval(secs=>(a.challenge->'delays'->>0)::numeric/1000),
    deadline=least(at_time+make_interval(secs=>((a.challenge->'delays'->>0)::numeric+(cfg->>'reaction_response_ms')::numeric)/1000),expires_at),
    revision=revision+1 where id=a.id;
  elsif a.phase='memory_ready' then
   update public.focus_attempts set phase='memory',step=0,
    signal_at=at_time+interval '1 second'+make_interval(secs=>((cfg->>'memory_flash_ms')::numeric+(cfg->>'memory_gap_ms')::numeric)*(cfg->>'memory_length')::numeric/1000),
    deadline=least(at_time+interval '1 second'+make_interval(secs=>(((cfg->>'memory_flash_ms')::numeric+(cfg->>'memory_gap_ms')::numeric)*(cfg->>'memory_length')::numeric+(cfg->>'memory_input_ms')::numeric)/1000),expires_at),
    revision=revision+1 where id=a.id;
  else
   update public.focus_attempts set phase='precision',signal_at=at_time,
    deadline=least(at_time+make_interval(secs=>(cfg->>'precision_ms')::numeric/1000),expires_at),revision=revision+1 where id=a.id;
  end if;
 elsif selected_action='reaction' and a.phase='reaction' then
  if coalesce(evidence->>'elapsed_ms','') !~ '^[0-9]{1,4}$' then raise exception 'focus_invalid_action'; end if;
  ms:=(evidence->>'elapsed_ms')::integer;
  if ms>(cfg->>'reaction_response_ms')::integer or at_time<a.signal_at then raise exception 'focus_invalid_action'; end if;
  update public.focus_attempts set reaction_ms=jsonb_build_array(ms) where id=a.id;
  perform public._focus_finish_stage(a.id,ms<=(cfg->>'reaction_median_ms')::integer,'reaction_slow',at_time);
 elsif selected_action='memory' and a.phase='memory' then
  if coalesce(evidence->>'cell','') !~ '^[0-8]$' or at_time<a.signal_at then raise exception 'focus_invalid_action'; end if;
  cell:=(evidence->>'cell')::integer;
  if cell<>(a.challenge->'memory'->>a.step)::integer then
   perform public._focus_finish_stage(a.id,false,'memory_wrong',at_time);
  elsif a.step+1=(cfg->>'memory_length')::integer then
   perform public._focus_finish_stage(a.id,true,null,at_time);
  else
   update public.focus_attempts set step=step+1,revision=revision+1 where id=a.id;
  end if;
 elsif selected_action='precision' and a.phase='precision' then
  taps:=evidence->'taps';
  if jsonb_typeof(taps) is distinct from 'array' or jsonb_array_length(taps) not between 1 and (cfg->>'precision_targets')::integer
   then raise exception 'focus_invalid_action'; end if;
  for i in 0..jsonb_array_length(taps)-1 loop
   if coalesce(taps->>i,'') !~ '^[0-9]{1,5}$' then raise exception 'focus_invalid_action'; end if;
   ms:=(taps->>i)::integer;
   if ms<=previous_ms or ms>(cfg->>'precision_ms')::integer or ms>extract(epoch from at_time-a.signal_at)*1000+250
    then raise exception 'focus_invalid_action'; end if;
   if i<jsonb_array_length(a.precision_taps) and taps->i<>a.precision_taps->i then raise exception 'focus_invalid_action'; end if;
   previous_ms:=ms;
  end loop;
  if jsonb_array_length(taps)>=jsonb_array_length(a.precision_taps) then
   update public.focus_attempts set precision_taps=taps where id=a.id;
   complete:=jsonb_array_length(taps)=(cfg->>'precision_targets')::integer;
   if complete then perform public._focus_finish_stage(a.id,true,null,at_time); end if;
  end if;
 else raise exception 'focus_invalid_action'; end if;
 select * into a from public.focus_attempts where id=target_attempt;
 return public._focus_public(a,at_time);
end $$;

-- Return the highest active effect, so a later partial QA win cannot downgrade it.
create or replace function public.focus_status(actor_player uuid,target_season uuid) returns jsonb
language plpgsql set search_path=public as $$
declare s public.seasons%rowtype; mid uuid; night date; n integer; failures integer; won boolean;
 a public.focus_attempts%rowtype; active_until timestamptz; multiplier numeric; at_time timestamptz:=statement_timestamp();
begin
 s:=public._focus_season(actor_player,target_season);
 perform pg_advisory_xact_lock(hashtext(s.lobby_id::text));
 select id into mid from public.lobby_memberships where lobby_id=s.lobby_id and player_id=actor_player;
 perform public._focus_expire(mid,s.id,at_time);
 night:=public._chug_night(at_time,s.timezone_name);
 select count(*) into n from public.drink_entries where membership_id=mid and season_id=s.id
  and rule_version='v1' and location_check_result in('matched','outside') and public._chug_night(submitted_at,s.timezone_name)=night;
 select count(*) filter(where status='failed'),coalesce(bool_or(status='passed'),false) into failures,won
  from public.focus_attempts where membership_id=mid and season_id=s.id and game_night=night;
 select boost_ends_at,boost_multiplier into active_until,multiplier from public.focus_attempts
  where membership_id=mid and season_id=s.id and status='passed' and boost_ends_at>at_time
  order by boost_multiplier desc,boost_ends_at desc,id limit 1;
 select * into a from public.focus_attempts where membership_id=mid and season_id=s.id order by started_at desc,id desc limit 1;
 return jsonb_build_object('flow_version',3,'count',n,'unlimited',public._focus_is_test(s),
  'threshold',case when public._focus_is_test(s) then 0 else (public._focus_rules(s)->>'first_unlock')::integer+failures*(public._focus_rules(s)->>'retry_step')::integer end,
  'won',won,'boost_ends_at',active_until,'boost_multiplier',coalesce(multiplier,1),
  'attempt',case when a.id is not null then public._focus_public(a,at_time) else null end,'server_now',at_time);
end $$;

create or replace function public._snapshot_focus_boost() returns trigger language plpgsql set search_path=public as $$
declare cfg jsonb;
begin
 if tg_op='UPDATE' then
  if new.focus_attempt_id is distinct from old.focus_attempt_id or new.focus_multiplier is distinct from old.focus_multiplier
   then raise exception 'entry_identity_frozen'; end if;
  return new;
 end if;
 new.focus_attempt_id:=null;new.focus_multiplier:=1;
 select public._focus_rules(s) into cfg from public.seasons s where id=new.season_id;
 if new.rule_version='v1' and cfg->>'version'='1' and not exists(select 1 from public.chug_duels
   where challenger_entry_id=new.id or opponent_entry_id=new.id) then
  select id,boost_multiplier into new.focus_attempt_id,new.focus_multiplier from public.focus_attempts where membership_id=new.membership_id
   and season_id=new.season_id and status='passed' and completed_at<=new.submitted_at and new.submitted_at<boost_ends_at
   order by boost_multiplier desc,boost_ends_at desc,id limit 1;
 end if;
 new.focus_multiplier:=coalesce(new.focus_multiplier,1);
 return new;
end $$;

-- Change only the multiplier expression in the installed replay function.
-- This retains independent Time Duel / absent-membership changes if installed.
do $$ declare definition text; old_expression text:='case when entry.focus_attempt_id is not null then 1.5 else 1 end'; begin
 select pg_get_functiondef('public._replay_scoring_season(uuid)'::regprocedure) into definition;
 if position(old_expression in definition)>0 then
  execute replace(definition,old_expression,'entry.focus_multiplier');
 elsif position('entry.focus_multiplier' in definition)=0 then
  raise exception 'focus_replay_upgrade_required';
 end if;
end $$;

revoke all on function public._focus_finish_stage(uuid,boolean,text,timestamptz),
 public.focus_attempt_action(uuid,uuid,integer,text,jsonb),public._focus_attempt_action_v2(uuid,uuid,integer,text,jsonb)
 from public,anon,authenticated;
grant execute on function public._focus_finish_stage(uuid,boolean,text,timestamptz),
 public.focus_attempt_action(uuid,uuid,integer,text,jsonb) to service_role;
notify pgrst,'reload schema';
commit;
