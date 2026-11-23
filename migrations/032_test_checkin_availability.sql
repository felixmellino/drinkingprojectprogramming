-- Requires 031. Existing test seasons use the frozen JSON boolean flag.
-- Chug Duel still checks the weekly window when inviting or expiring a duel,
-- including before start_chug_duel calls this shared check-in function.

create or replace function public.accept_scoring_checkin(
  actor_player uuid, capture_id uuid, member_id uuid, target_season uuid,
  selected_drink text, selected_size text, verified_territory text,
  location_result text, stored_photo text, photo_received_at timestamptz
)
returns setof public.drink_entries language plpgsql set search_path = public as $$
declare
  season public.seasons%rowtype;
  existing public.drink_entries%rowtype;
  received_at timestamptz := statement_timestamp();
  is_test boolean;
  points integer;
  last_submission timestamptz;
  amount_ml double precision;
begin
  perform public._require_active_lobby(actor_player,(select lobby_id from public.seasons where id=target_season));
  select s.* into season from public.seasons s join public.active_lobby_memberships m on m.lobby_id = s.lobby_id
    where s.id = target_season and m.id = member_id and m.player_id = actor_player;
  if not found then raise exception 'permission_denied'; end if;
  -- One lobby lock also protects the cross-season, per-membership cooldown.
  perform pg_advisory_xact_lock(hashtext(season.lobby_id::text));
  select * into existing from public.drink_entries where id = capture_id;
  if found then
    if existing.membership_id <> member_id or existing.season_id <> target_season then
      raise exception 'permission_denied';
    end if;
    return query select * from public.drink_entries where id = capture_id;
    return;
  end if;
  if season.scoring_version <> 'v1' or season.scoring_rules is null then raise exception 'scoring_setup_required'; end if;
  is_test := season.scoring_rules->'test_mode' is not distinct from 'true'::jsonb;
  if received_at < season.starts_at or received_at >= season.ends_at
    or (not is_test and not public._scoring_window_open(received_at, season.timezone_name, season.scoring_rules)) then
    raise exception 'scoring_closed';
  end if;
  points := public._scoring_points(season.scoring_rules, selected_drink, selected_size);
  if location_result is null or location_result not in ('matched','outside') then raise exception 'location_unavailable'; end if;
  if (location_result = 'matched' and (verified_territory is null or not exists(select 1 from public.territories where id = verified_territory)))
      or (location_result = 'outside' and verified_territory is not null) then raise exception 'invalid_territory'; end if;
  if stored_photo is distinct from season.lobby_id::text || '/' || capture_id::text || '.jpg' then raise exception 'invalid_photo'; end if;
  if photo_received_at is null or photo_received_at > received_at then raise exception 'invalid_photo'; end if;
  if not is_test then
    select max(submitted_at) into last_submission from public.drink_entries where membership_id = member_id;
    if last_submission is not null and received_at < last_submission + make_interval(secs => (season.scoring_rules->>'cooldown_seconds')::integer) then
      raise exception 'cooldown';
    end if;
  end if;
  amount_ml := (season.scoring_rules -> 'volumes' -> selected_drink ->> selected_size)::double precision;
  insert into public.drink_entries(id,membership_id,season_id,drink_type,amount,size,photo_ref,photo_captured_at,
    territory_id,location_check_result,points_awarded,submitted_at,rule_version)
  values(capture_id,member_id,target_season,selected_drink,amount_ml,
    case when selected_drink = 'shot' then null else selected_size end,stored_photo,photo_received_at,
    verified_territory,location_result,points,received_at,'v1');
  perform public._replay_scoring_season(target_season);
  return query select * from public.drink_entries where id = capture_id;
end;
$$;
