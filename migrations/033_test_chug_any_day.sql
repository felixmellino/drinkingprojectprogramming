-- Requires 032. Test seasons (frozen JSON flag scoring_rules.test_mode=true)
-- allow Chug Duel on any day of the season, like ordinary check-ins (032)
-- and the Quiz, Time and Reaction Duels (_quiz_open). Standard seasons keep
-- the weekly Thursday 18:00-Sunday 18:00 window. Safe to run twice.

create or replace function public._chug_open(s public.seasons, at_time timestamptz)
returns boolean language sql stable set search_path = public as $$
  select at_time >= s.starts_at and at_time < s.ends_at
    and (s.scoring_rules->'test_mode' is not distinct from 'true'::jsonb
         or public._scoring_window_open(at_time, s.timezone_name, s.scoring_rules));
$$;

create or replace function public._expire_chug_duels(lid uuid,at_time timestamptz)
returns void language plpgsql set search_path = public as $$
begin
  update public.chug_duels d set status = case d.status
      when 'started' then 'aborted' when 'accepted' then 'cancelled' else 'expired' end,
    finished_at = at_time
    from public.seasons s where s.id=d.season_id and s.lobby_id=lid
      and d.status in ('invited','accepted','started')
      and (at_time >= d.expires_at
        or d.game_night <> public._chug_night(at_time,s.timezone_name)
        or not public._chug_open(s,at_time));
end $$;

create or replace function public.invite_chug_duel(actor_player uuid,target_season uuid,
  invitation_id uuid,opponent_member uuid,selected_drink text,selected_size text)
returns setof public.chug_duels language plpgsql set search_path = public as $$
declare s public.seasons%rowtype; cid uuid; at_time timestamptz := statement_timestamp(); night date;
  old public.chug_duels%rowtype;
begin
  select * into s from public.seasons where id=target_season;
  if not found then raise exception 'permission_denied'; end if;
  perform pg_advisory_xact_lock(hashtext(s.lobby_id::text));
  select id into cid from public.active_lobby_memberships where lobby_id=s.lobby_id and player_id=actor_player;
  if cid is null then raise exception 'permission_denied'; end if;
  perform public._expire_chug_duels(s.lobby_id,at_time);
  select * into old from public.chug_duels where id=invitation_id;
  if found then
    if old.challenger_id<>cid or old.season_id<>target_season or old.opponent_id<>opponent_member
      or old.drink_type is distinct from selected_drink or old.size is distinct from selected_size then
      raise exception 'permission_denied';
    end if;
    return query select * from public.chug_duels where id=invitation_id; return;
  end if;
  if s.scoring_version<>'v1' or s.scoring_rules is null then raise exception 'scoring_setup_required'; end if;
  if not public._chug_open(s,at_time) then raise exception 'scoring_closed'; end if;
  perform public._scoring_points(s.scoring_rules,selected_drink,selected_size);
  perform public._check_chug_pair(cid,opponent_member,s.lobby_id);
  night := public._chug_night(at_time,s.timezone_name);
  perform public._check_chug_slots(cid,opponent_member,night,invitation_id);
  if exists(select 1 from public.chug_duels where challenger_id=cid and status='invited') then raise exception 'duel_pending'; end if;
  insert into public.chug_duels(id,season_id,challenger_id,opponent_id,game_night,drink_type,size,created_at,expires_at)
    values(invitation_id,target_season,cid,opponent_member,night,selected_drink,selected_size,at_time,at_time+interval '10 minutes');
  return query select * from public.chug_duels where id=invitation_id;
end $$;

-- The Games tile badge counts a Chug invitation whenever the duel can be played.
create or replace function public.pending_minigame_invites(actor_player uuid, target_season uuid)
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
        and public._chug_open(r.s, r.at_time)),
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

-- The new helper and the replaced functions stay private to the trusted Streamlit service.
do $$ declare f record; begin
 for f in select oid::regprocedure signature from pg_proc where pronamespace='public'::regnamespace
 and proname in('_chug_open','_expire_chug_duels','invite_chug_duel','pending_minigame_invites') loop
  execute format('revoke all on function %s from public,anon,authenticated',f.signature);
  execute format('grant execute on function %s to service_role',f.signature);
 end loop;
end $$;
notify pgrst,'reload schema';
