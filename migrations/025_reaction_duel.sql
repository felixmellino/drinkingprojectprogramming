-- Reaction Duel: replaces the solo Reaction Test (Focus) on the Games tab.
-- Requires 016_quiz_duel.sql and 017_time_duel.sql. Safe to run twice.
-- A player challenges another lobby member for a stake of 1-10 season points.
-- After acceptance both play three reaction tries on their own phone. Try n of
-- one player is compared with try n of the other: the faster time wins the round.
-- More rounds wins; equal rounds -> lower total time; equal total -> draw.
-- The loser's stake goes to the winner through the shared quiz_transfers ledger,
-- so standings, profile stats and reserved-point checks need no new code.
begin;
create table if not exists public.reaction_duels (
 id uuid primary key, season_id uuid not null references public.seasons(id),
 challenger_id uuid not null references public.lobby_memberships(id),
 opponent_id uuid not null references public.lobby_memberships(id),
 game_night date not null, stake integer not null check(stake between 1 and 10),
 status text not null default 'invited'
  check(status in('invited','accepted','completed','draw','declined','cancelled','expired')),
 created_at timestamptz not null, expires_at timestamptz not null,
 accepted_at timestamptz, finished_at timestamptz,
 challenger_account uuid, opponent_account uuid,
 winner_id uuid references public.lobby_memberships(id), reason text,
 round_results jsonb not null default '[]',
 check(challenger_id<>opponent_id),
 check(winner_id is null or winner_id in(challenger_id,opponent_id)),
 check(status<>'completed' or winner_id is not null)
);
create index if not exists reaction_season on public.reaction_duels(season_id,created_at desc);
create unique index if not exists reaction_pending on public.reaction_duels(challenger_id,season_id) where status='invited';
-- One row per player and duel: their tries so far and the next signal.
-- A missed try is stored as 9999 ms, slower than any real tap.
create table if not exists public.reaction_runs (
 duel_id uuid not null references public.reaction_duels(id),
 membership_id uuid not null references public.lobby_memberships(id),
 step integer not null default 0 check(step between 0 and 3),
 times integer[] not null default '{}',
 signal_at timestamptz, deadline timestamptz, revision integer not null default 0,
 primary key(duel_id,membership_id)
);
alter table public.reaction_duels enable row level security;
alter table public.reaction_runs enable row level security;
revoke all on public.reaction_duels,public.reaction_runs from public,anon,authenticated;
grant all on public.reaction_duels,public.reaction_runs to service_role;

-- Stakes of every game share one ledger. Reaction stakes may be 1 or 2 points.
alter table public.quiz_transfers drop constraint if exists quiz_transfers_id_fkey;
alter table public.quiz_transfers drop constraint if exists quiz_transfers_points_check;
alter table public.quiz_transfers add constraint quiz_transfers_points_check check(points between 1 and 10);

create or replace function public._reaction_rules() returns jsonb language sql immutable as $$
 select '{"version":1,"min_stake":1,"max_stake":10,"reaction_trials":3,"reaction_response_ms":2000,
 "reaction_min_ms":100,"reaction_wait_min_ms":3500,"reaction_wait_max_ms":6500,
 "invitation_seconds":600,"game_seconds":900,"miss_ms":9999}'::jsonb
$$;

-- Accepted reaction stakes are reserved exactly like accepted quiz stakes.
create or replace function public._quiz_reserved(sid uuid,account uuid) returns numeric
language sql stable set search_path=public as $$
 select coalesce((select sum(stake) from public.quiz_duels where season_id=sid
 and status in('accepted','playing','between') and account in(challenger_account,opponent_account)),0)
 +coalesce((select sum(stake) from public.reaction_duels where season_id=sid
 and status='accepted' and account in(challenger_account,opponent_account)),0)
$$;
create or replace function public._quiz_check_account(sid uuid,account uuid) returns void
language plpgsql set search_path=public as $$
begin
 if account is null then return; end if;
 if exists(select 1 from public.quiz_duels where season_id=sid and status in('accepted','playing','between')
  and account in(challenger_account,opponent_account))
  or exists(select 1 from public.reaction_duels where season_id=sid and status='accepted'
  and account in(challenger_account,opponent_account))
  or exists(select 1 from public.quiz_transfers where season_id=sid and account in(source_id,target_id)) then
  if public._quiz_balance(sid,account)<public._quiz_reserved(sid,account) then raise exception 'quiz_reserved_points'; end if;
 end if;
end $$;

create or replace function public._reaction_wait() returns interval language sql volatile as $$
 select make_interval(secs=>(3500+floor(random()*3001))/1000.0)
$$;

-- Decide a finished duel from both players' three times.
create or replace function public._reaction_settle(d public.reaction_duels,at_time timestamptz,why text)
returns public.reaction_duels language plpgsql set search_path=public as $$
declare a integer[]; b integer[]; i integer; a_wins integer:=0; b_wins integer:=0; winner uuid;
 results jsonb:='[]'; round_winner uuid;
begin
 select times into a from public.reaction_runs where duel_id=d.id and membership_id=d.challenger_id;
 select times into b from public.reaction_runs where duel_id=d.id and membership_id=d.opponent_id;
 a:=coalesce(a,'{}'); b:=coalesce(b,'{}');
 -- Tries that were never played count as misses.
 while coalesce(array_length(a,1),0)<3 loop a:=a||9999; end loop;
 while coalesce(array_length(b,1),0)<3 loop b:=b||9999; end loop;
 for i in 1..3 loop
  round_winner:=case when a[i]<b[i] then d.challenger_id when b[i]<a[i] then d.opponent_id end;
  a_wins:=a_wins+case when round_winner=d.challenger_id then 1 else 0 end;
  b_wins:=b_wins+case when round_winner=d.opponent_id then 1 else 0 end;
  results:=results||jsonb_build_object('round_no',i,'challenger_ms',a[i],'opponent_ms',b[i],'winner_id',round_winner);
 end loop;
 winner:=case when a_wins>b_wins then d.challenger_id when b_wins>a_wins then d.opponent_id
  when (a[1]+a[2]+a[3])<(b[1]+b[2]+b[3]) then d.challenger_id
  when (b[1]+b[2]+b[3])<(a[1]+a[2]+a[3]) then d.opponent_id end;
 update public.reaction_duels set status=case when winner is null then 'draw' else 'completed' end,
  winner_id=winner,finished_at=at_time,reason=why,round_results=results where id=d.id returning * into d;
 if winner is not null then
  insert into public.quiz_transfers(id,season_id,source_id,target_id,source_membership_id,target_membership_id,points,created_at)
  values(d.id,d.season_id,case when winner=d.challenger_id then d.opponent_account else d.challenger_account end,
  case when winner=d.challenger_id then d.challenger_account else d.opponent_account end,
  case when winner=d.challenger_id then d.opponent_id else d.challenger_id end,winner,d.stake,at_time)
  on conflict(id) do nothing;
 end if;
 update public.reaction_runs set signal_at=null,deadline=null,revision=revision+1 where duel_id=d.id;
 return d;
end $$;

-- Expire old invitations, end games whose time ran out, settle games both finished.
create or replace function public._reaction_refresh(s public.seasons,at_time timestamptz) returns void
language plpgsql set search_path=public as $$
declare d public.reaction_duels%rowtype;
begin
 update public.reaction_duels set status='expired',finished_at=expires_at,reason='timeout'
  where season_id=s.id and status='invited' and at_time>=expires_at;
 for d in select * from public.reaction_duels where season_id=s.id and status='accepted' order by created_at,id for update loop
  if at_time>=d.expires_at then
   perform public._reaction_settle(d,d.expires_at,'timeout');
  elsif (select count(*) from public.reaction_runs where duel_id=d.id and step=3)=2 then
   perform public._reaction_settle(d,at_time,'rounds');
  end if;
 end loop;
end $$;

create or replace function public._reaction_public(d public.reaction_duels,viewer uuid,at_time timestamptz)
returns jsonb language sql stable set search_path=public as $$
 select (to_jsonb(d)-'challenger_account'-'opponent_account')||jsonb_build_object('server_now',at_time,
 'config',public._reaction_rules(),
 -- The viewer's own run, in the shape the play component expects.
 'run',(select jsonb_build_object('id',d.id,'revision',r.revision,
   'status',case when d.status='accepted' and r.step<3 then 'running' else 'done' end,
   'phase',case when r.signal_at is null and r.step=0 then 'reaction_ready' else 'reaction' end,
   'step',r.step,'reaction_ms',to_jsonb(r.times),'signal_at',r.signal_at,'deadline',r.deadline,
   'expires_at',d.expires_at,'server_now',at_time,'config',public._reaction_rules())
   from public.reaction_runs r where r.duel_id=d.id and r.membership_id=viewer),
 -- The opponent's progress only; their times stay hidden until the duel ends.
 'other_step',(select r.step from public.reaction_runs r where r.duel_id=d.id and r.membership_id<>viewer))
$$;

create or replace function public._reaction_season(actor_player uuid,target_season uuid)
returns public.seasons language plpgsql set search_path=public as $$
declare s public.seasons%rowtype;
begin
 select season.* into s from public.seasons season join public.active_lobby_memberships m on m.lobby_id=season.lobby_id
 where season.id=target_season and m.player_id=actor_player;
 if not found then raise exception 'permission_denied'; end if;
 if s.scoring_version<>'v1' then raise exception 'scoring_closed'; end if;
 return s;
end $$;

-- Normal seasons: one outgoing and one incoming accepted duel per 06:00-based night.
create or replace function public._reaction_slots(d public.reaction_duels,s public.seasons) returns void
language plpgsql set search_path=public as $$
begin
 if coalesce(s.scoring_rules->>'test_mode'='true',false) then return; end if;
 if exists(select 1 from public.reaction_duels where season_id=s.id and id<>d.id and game_night=d.game_night
  and accepted_at is not null and (challenger_id=d.challenger_id or opponent_id=d.opponent_id)) then
  raise exception 'reaction_limit'; end if;
end $$;

create or replace function public.reaction_status(actor_player uuid,target_season uuid) returns jsonb
language plpgsql set search_path=public as $$
declare s public.seasons%rowtype; mid uuid; account uuid; night date; items jsonb; qa boolean;
 at_time timestamptz:=statement_timestamp();
begin
 s:=public._reaction_season(actor_player,target_season);
 perform pg_advisory_xact_lock(hashtext(s.lobby_id::text));
 perform public._reaction_refresh(s,at_time);
 select id,coalesce(team_id,id) into mid,account from public.lobby_memberships where lobby_id=s.lobby_id and player_id=actor_player;
 night:=public._chug_night(at_time,s.timezone_name); qa:=coalesce(s.scoring_rules->>'test_mode'='true',false);
 select coalesce(jsonb_agg(public._reaction_public(d,mid,at_time) order by (d.status in('invited','accepted')) desc,d.created_at desc),'[]')
  into items from (select * from public.reaction_duels where season_id=s.id and mid in(challenger_id,opponent_id)
  order by (status in('invited','accepted')) desc,created_at desc limit 20) d;
 return jsonb_build_object('duels',items,
  'available_points',public._quiz_balance(s.id,account)-public._quiz_reserved(s.id,account),
  'outgoing',qa or not exists(select 1 from public.reaction_duels where season_id=s.id and game_night=night
   and challenger_id=mid and accepted_at is not null),
  'incoming',qa or not exists(select 1 from public.reaction_duels where season_id=s.id and game_night=night
   and opponent_id=mid and accepted_at is not null),
  'test_mode',qa,'open',public._quiz_open(s,at_time),'server_now',at_time,'config',public._reaction_rules());
end $$;

create or replace function public.invite_reaction_duel(actor_player uuid,target_season uuid,invitation_id uuid,
 opponent_member uuid,selected_stake integer) returns jsonb
language plpgsql set search_path=public as $$
declare s public.seasons%rowtype; d public.reaction_duels%rowtype; cid uuid; ca uuid; oa uuid;
 at_time timestamptz:=statement_timestamp();
begin
 s:=public._reaction_season(actor_player,target_season);
 perform pg_advisory_xact_lock(hashtext(s.lobby_id::text));
 perform public._reaction_refresh(s,at_time);
 select id,coalesce(team_id,id) into cid,ca from public.lobby_memberships where lobby_id=s.lobby_id and player_id=actor_player;
 select * into d from public.reaction_duels where id=invitation_id;
 if found then   -- a retried request returns the original invitation
  if d.challenger_id<>cid or d.season_id<>s.id then raise exception 'permission_denied'; end if;
  return public._reaction_public(d,cid,at_time);
 end if;
 if not public._quiz_open(s,at_time) then raise exception 'scoring_closed'; end if;
 if selected_stake is null or selected_stake not between 1 and 10 then raise exception 'reaction_stake'; end if;
 begin perform public._check_chug_pair(cid,opponent_member,s.lobby_id);
 exception when raise_exception then if sqlerrm='duel_team' then raise exception 'reaction_team'; else raise; end if; end;
 select coalesce(team_id,id) into oa from public.lobby_memberships where id=opponent_member;
 d.id:=invitation_id;d.season_id:=s.id;d.challenger_id:=cid;d.opponent_id:=opponent_member;
 d.game_night:=public._chug_night(at_time,s.timezone_name);
 perform public._reaction_slots(d,s);
 if exists(select 1 from public.reaction_duels where challenger_id=cid and season_id=s.id and status='invited') then
  raise exception 'reaction_pending'; end if;
 if public._quiz_balance(s.id,ca)-public._quiz_reserved(s.id,ca)<selected_stake
  or public._quiz_balance(s.id,oa)-public._quiz_reserved(s.id,oa)<selected_stake then raise exception 'reaction_funds'; end if;
 insert into public.reaction_duels(id,season_id,challenger_id,opponent_id,game_night,stake,created_at,expires_at)
 values(d.id,s.id,cid,opponent_member,d.game_night,selected_stake,at_time,
  least(at_time+interval '10 minutes',public._quiz_end(s,at_time))) returning * into d;
 return public._reaction_public(d,cid,at_time);
end $$;

create or replace function public.reaction_action(actor_player uuid,target_duel uuid,selected_action text,
 expected_revision integer default null,elapsed_ms integer default null) returns jsonb
language plpgsql set search_path=public as $$
declare s public.seasons%rowtype; d public.reaction_duels%rowtype; r public.reaction_runs%rowtype;
 mid uuid; ca uuid; oa uuid; at_time timestamptz:=statement_timestamp();
begin
 select * into d from public.reaction_duels where id=target_duel;
 if not found then raise exception 'permission_denied'; end if;
 s:=public._reaction_season(actor_player,d.season_id);
 select id into mid from public.lobby_memberships where lobby_id=s.lobby_id and player_id=actor_player;
 if mid not in(d.challenger_id,d.opponent_id) then raise exception 'permission_denied'; end if;
 perform pg_advisory_xact_lock(hashtext(s.lobby_id::text));
 perform public._reaction_refresh(s,at_time);
 select * into d from public.reaction_duels where id=target_duel;
 if d.status not in('invited','accepted') then return public._reaction_public(d,mid,at_time); end if;
 if selected_action='accept' and mid=d.opponent_id and d.status='invited' then
  if not public._quiz_open(s,at_time) then raise exception 'scoring_closed'; end if;
  begin perform public._check_chug_pair(d.challenger_id,d.opponent_id,s.lobby_id);
  exception when raise_exception then if sqlerrm='duel_team' then raise exception 'reaction_team'; else raise; end if; end;
  perform public._reaction_slots(d,s);
  if exists(select 1 from public.reaction_duels where season_id=s.id and status='accepted' and id<>d.id
   and (challenger_id in(d.challenger_id,d.opponent_id) or opponent_id in(d.challenger_id,d.opponent_id))) then
   raise exception 'reaction_busy'; end if;
  select coalesce(team_id,id) into ca from public.lobby_memberships where id=d.challenger_id;
  select coalesce(team_id,id) into oa from public.lobby_memberships where id=d.opponent_id;
  if public._quiz_balance(s.id,ca)-public._quiz_reserved(s.id,ca)<d.stake
   or public._quiz_balance(s.id,oa)-public._quiz_reserved(s.id,oa)<d.stake then raise exception 'reaction_funds'; end if;
  update public.reaction_duels set status='accepted',accepted_at=at_time,challenger_account=ca,opponent_account=oa,
   expires_at=least(at_time+interval '15 minutes',public._quiz_end(s,at_time)) where id=d.id returning * into d;
  insert into public.reaction_runs(duel_id,membership_id) values(d.id,d.challenger_id),(d.id,d.opponent_id)
   on conflict do nothing;
  return public._reaction_public(d,mid,at_time);
 elsif selected_action='decline' and mid=d.opponent_id and d.status='invited' then
  update public.reaction_duels set status='declined',finished_at=at_time,reason='declined' where id=d.id returning * into d;
  return public._reaction_public(d,mid,at_time);
 elsif selected_action='cancel' and mid=d.challenger_id and d.status='invited' then
  update public.reaction_duels set status='cancelled',finished_at=at_time,reason='cancelled' where id=d.id returning * into d;
  return public._reaction_public(d,mid,at_time);
 elsif selected_action not in('ready','reaction','false_start','miss') or d.status<>'accepted' then
  raise exception 'reaction_unavailable';
 end if;
 select * into r from public.reaction_runs where duel_id=d.id and membership_id=mid for update;
 -- A retry of an already saved tap (old revision) just returns the current state.
 if expected_revision is distinct from r.revision or r.step>=3 then return public._reaction_public(d,mid,at_time); end if;
 if selected_action='ready' then
  if r.signal_at is null then
   update public.reaction_runs set signal_at=at_time+public._reaction_wait(),revision=revision+1
    where duel_id=d.id and membership_id=mid returning * into r;
   update public.reaction_runs set deadline=signal_at+interval '2 seconds' where duel_id=d.id and membership_id=mid;
  end if;
 elsif r.signal_at is null then
  raise exception 'reaction_unavailable';
 elsif selected_action='false_start' then
  -- Tapped before the signal: the try does not count and starts again with a new wait.
  -- Claiming a false start only costs the player time, so it is always accepted.
  update public.reaction_runs set signal_at=at_time+public._reaction_wait(),revision=revision+1
   where duel_id=d.id and membership_id=mid returning * into r;
  update public.reaction_runs set deadline=signal_at+interval '2 seconds' where duel_id=d.id and membership_id=mid;
 else
  if selected_action='reaction' then
   if elapsed_ms is null or elapsed_ms not between 100 and 2000 then raise exception 'reaction_invalid'; end if;
   -- The phone measures the time; the tap must still reach the server after the signal.
   if at_time<r.signal_at or at_time>r.deadline+interval '5 seconds' then raise exception 'reaction_invalid'; end if;
  else  -- miss (no tap in time): a slower result than any tap, so it only hurts the sender
   elapsed_ms:=9999;
  end if;
  update public.reaction_runs set times=times||elapsed_ms,step=step+1,revision=revision+1,
   signal_at=case when step+1<3 then at_time+public._reaction_wait() end
   where duel_id=d.id and membership_id=mid returning * into r;
  update public.reaction_runs set deadline=signal_at+interval '2 seconds' where duel_id=d.id and membership_id=mid;
  if (select count(*) from public.reaction_runs where duel_id=d.id and step=3)=2 then
   d:=public._reaction_settle(d,at_time,'rounds');
  end if;
 end if;
 return public._reaction_public(d,mid,at_time);
end $$;

-- Badges on the Games tab: count pending reaction invitations too.
drop function if exists public.pending_minigame_invite_count(uuid,uuid);
drop function if exists public.pending_minigame_invites(uuid,uuid);
create function public.pending_minigame_invites(actor_player uuid, target_season uuid)
returns table(chug bigint, quiz bigint, "time" bigint, reaction bigint)
language sql stable set search_path = public as $$
  with recipient as (
    select m.id, s, statement_timestamp() as at_time
    from public.seasons s
    join public.active_lobby_memberships m on m.lobby_id = s.lobby_id
    where s.id = target_season and m.player_id = actor_player
      and s.scoring_version = 'v1'
      and statement_timestamp() >= s.starts_at and statement_timestamp() < s.ends_at
  )
  select
    (select count(*) from recipient r
      join public.chug_duels d on d.opponent_id = r.id and d.season_id = (r.s).id
      where d.status = 'invited' and d.expires_at > r.at_time
        and d.game_night = public._chug_night(r.at_time, (r.s).timezone_name)
        and public._scoring_window_open(r.at_time, (r.s).timezone_name, (r.s).scoring_rules)),
    (select count(*) from recipient r
      join public.quiz_duels d on d.opponent_id = r.id and d.season_id = (r.s).id
      where d.status = 'invited' and d.expires_at > r.at_time),
    (select count(*) from recipient r
      join public.time_duels d on d.opponent_id = r.id and d.season_id = (r.s).id
      where d.status = 'invited' and d.expires_at > r.at_time),
    (select count(*) from recipient r
      join public.reaction_duels d on d.opponent_id = r.id and d.season_id = (r.s).id
      where d.status = 'invited' and d.expires_at > r.at_time);
$$;
create function public.pending_minigame_invite_count(actor_player uuid, target_season uuid)
returns bigint language sql stable set search_path = public as $$
  select chug + quiz + "time" + reaction from public.pending_minigame_invites(actor_player, target_season);
$$;

-- Every helper and RPC stays private to the trusted Streamlit service.
do $$ declare f record; begin
 for f in select oid::regprocedure signature from pg_proc where pronamespace='public'::regnamespace
 and (proname like '\_reaction\_%' escape '\' or proname in('reaction_status','invite_reaction_duel','reaction_action',
  'pending_minigame_invites','pending_minigame_invite_count','_quiz_reserved','_quiz_check_account')) loop
  execute format('revoke all on function %s from public,anon,authenticated',f.signature);
  execute format('grant execute on function %s to service_role',f.signature);
 end loop;
end $$;
notify pgrst,'reload schema';
commit;
