-- Requires 026 and the documented scoring, team and minigame migrations.
begin;

create table public.territory_boosts (
  id uuid primary key default gen_random_uuid(),
  season_id uuid not null references public.seasons(id),
  territory_id text not null references public.territories(id),
  starts_at timestamptz not null,
  ends_at timestamptz not null check (ends_at = starts_at + interval '15 minutes'),
  unique (season_id, starts_at)
);
alter table public.territory_boosts enable row level security;
revoke all on public.territory_boosts from public, anon, authenticated;
grant select, insert on public.territory_boosts to service_role;

alter table public.drink_entries add column territory_boost_id uuid references public.territory_boosts(id);
create index territory_boost_activity on public.drink_entries(season_id, territory_id, submitted_at)
  where rule_version = 'v1' and location_check_result = 'matched' and duel_id is null;

create function public._snapshot_territory_boost()
returns trigger language plpgsql set search_path = public as $$
begin
  if tg_op = 'UPDATE' then
    if new.territory_boost_id is distinct from old.territory_boost_id then
      raise exception 'entry_identity_frozen';
    end if;
    return new;
  end if;
  new.territory_boost_id := null;
  -- Chug Duel has already reserved both capture IDs before inserting either entry.
  if new.rule_version = 'v1' and new.location_check_result = 'matched'
    and not exists (select 1 from public.chug_duels
                    where new.id in (challenger_entry_id, opponent_entry_id)) then
    select b.id into new.territory_boost_id
      from public.territory_boosts b
      where b.season_id = new.season_id and b.territory_id = new.territory_id
        and b.starts_at <= new.submitted_at and new.submitted_at < b.ends_at;
  end if;
  return new;
end
$$;
create trigger snapshot_territory_boost before insert or update of territory_boost_id on public.drink_entries
  for each row execute function public._snapshot_territory_boost();

create function public.accept_territory_scoring_checkin(
  actor_player uuid, capture_id uuid, member_id uuid, target_season uuid,
  selected_drink text, selected_size text, verified_territory text,
  location_result text, stored_photo text, photo_received_at timestamptz, reachable_territories text[]
)
returns setof public.drink_entries language plpgsql set search_path = public as $$
declare
  season public.seasons%rowtype;
  entry public.drink_entries%rowtype;
  already_saved boolean;
  boost_area text;
begin
  select * into season from public.seasons where id = target_season;
  -- Reuse the existing lobby transaction lock so simultaneous check-ins and retries cannot draw twice.
  perform public._require_active_lobby(actor_player, season.lobby_id);
  select exists(select 1 from public.drink_entries where id = capture_id) into already_saved;
  select * into strict entry from public.accept_scoring_checkin(
    actor_player, capture_id, member_id, target_season, selected_drink, selected_size,
    verified_territory, location_result, stored_photo, photo_received_at);

  if not already_saved and season.scoring_rules->'territory_boost' = 'true'::jsonb
    and entry.location_check_result = 'matched' and entry.duel_id is null
    and entry.submitted_at + interval '15 minutes' <= public._focus_window_end(season, entry.submitted_at)
    and not exists (select 1 from public.territory_boosts b where b.season_id = target_season
                    and b.starts_at > entry.submitted_at - interval '150 minutes')
    and exists (
      select 1 from public.drink_entries prior
      where prior.season_id = target_season and prior.territory_id = entry.territory_id
        and prior.rule_version = 'v1' and prior.location_check_result = 'matched' and prior.duel_id is null
        and prior.event_order < entry.event_order
        and prior.submitted_at between entry.submitted_at - interval '30 minutes' and entry.submitted_at
        and coalesce(prior.team_id, prior.membership_id) <> coalesce(entry.team_id, entry.membership_id)
    ) then
    -- The app server supplies the current GeoJSON's two-border candidate list.
    select t.id into boost_area from public.territories t
      where t.id = entry.territory_id or t.id = any(reachable_territories)
      order by random() limit 1;
    -- This insert follows the trigger check-in, so the check-in that starts the boost earns its usual points.
    insert into public.territory_boosts(season_id, territory_id, starts_at, ends_at)
      values (target_season, boost_area, entry.submitted_at, entry.submitted_at + interval '15 minutes');
  end if;
  return next entry;
end
$$;

create function public.active_territory_boost(actor_player uuid, target_season uuid)
returns table (territory_id text, ends_at timestamptz) language plpgsql stable set search_path = public as $$
begin
  if not exists (select 1 from public.seasons s
    join public.active_lobby_memberships m on m.lobby_id = s.lobby_id
    where s.id = target_season and m.player_id = actor_player) then
    raise exception 'permission_denied';
  end if;
  return query select b.territory_id, b.ends_at
    from public.territory_boosts b where b.season_id = target_season
      and b.starts_at <= statement_timestamp() and statement_timestamp() < b.ends_at;
end
$$;

create or replace function public._replay_scoring_season(target_season uuid)
returns void language plpgsql set search_path = public as $$
declare
  entry public.drink_entries%rowtype; rules jsonb;
  totals jsonb := '{}'; owners jsonb := '{}';
  territory text; member text; prior_owner text; base numeric; multiplier numeric; points numeric; new_total numeric;
begin
  select scoring_rules into rules from public.seasons where id = target_season and scoring_version = 'v1';
  if rules is null then raise exception 'scoring_setup_required'; end if;
  for entry in select * from public.drink_entries where season_id = target_season order by event_order loop
    base := public._scoring_points(rules, entry.drink_type, entry.size);
    -- Older installs record only the Focus attempt ID. Preserve their x1.5 rule.
    multiplier := greatest(
      coalesce((to_jsonb(entry)->>'focus_multiplier')::numeric,
               case when entry.focus_attempt_id is null then 1 else 1.5 end),
      case when entry.territory_boost_id is null then 1 else 1.25 end);
    points := base * multiplier;
    territory := case when entry.location_check_result = 'matched' then entry.territory_id else null end;
    member := coalesce(entry.team_id,entry.membership_id)::text;
    prior_owner := case when territory is not null then owners ->> territory else null end;
    update public.drink_entries set points_awarded = points,
      time_bonus = case when entry.time_duel_id is not null and multiplier = 1
        then base * 0.25 else 0 end,
      owner_membership_id = case when entry.team_id is null and prior_owner is not null and prior_owner <> member
        and (entry.team_id is not null or not (prior_owner::uuid = any(entry.absent_member_ids))) then prior_owner::uuid else null end,
      owner_team_id = case when entry.team_id is not null and prior_owner is not null and prior_owner <> member
        and (entry.team_id is not null or not (prior_owner::uuid = any(entry.absent_member_ids))) then prior_owner::uuid else null end,
      owner_bonus_quarters = case when prior_owner is not null and prior_owner <> member
        and (entry.team_id is not null or not (prior_owner::uuid = any(entry.absent_member_ids))) then points else 0 end
      where id = entry.id;
    if territory is not null then
      new_total := coalesce((totals -> territory ->> member)::numeric, 0) + points;
      totals := jsonb_set(totals, array[territory],
        coalesce(totals -> territory, '{}'::jsonb) || jsonb_build_object(member,new_total),true);
      if prior_owner is null or new_total > (totals -> territory ->> prior_owner)::numeric then
        owners := owners || jsonb_build_object(territory,member);
      end if;
    end if;
  end loop;
end $$;

revoke all on function public._snapshot_territory_boost(),
 public.accept_territory_scoring_checkin(uuid,uuid,uuid,uuid,text,text,text,text,text,timestamptz,text[]),
 public.active_territory_boost(uuid,uuid) from public, anon, authenticated;
grant execute on function public._snapshot_territory_boost(),
 public.accept_territory_scoring_checkin(uuid,uuid,uuid,uuid,text,text,text,text,text,timestamptz,text[]),
 public.active_territory_boost(uuid,uuid) to service_role;
notify pgrst, 'reload schema';
commit;
