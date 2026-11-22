-- A creator can advance the cutoff once for an explicitly flagged test season.
begin;
alter table public.seasons add column if not exists ended_early boolean not null default false;

create or replace function public._freeze_scoring_season()
returns trigger language plpgsql set search_path = public as $$
begin
  if old.scoring_version = 'v1' and
     row(new.lobby_id, new.timezone_name, new.scoring_version, new.scoring_rules, new.starts_at, new.length_choice)
       is distinct from row(old.lobby_id, old.timezone_name, old.scoring_version, old.scoring_rules, old.starts_at, old.length_choice) then
    raise exception 'season_rules_frozen';
  end if;
  if new.ended_early is distinct from old.ended_early
     or (old.scoring_version = 'v1' and new.ends_at is distinct from old.ends_at) then
    if not (public._focus_is_test(old) and not old.ended_early and new.ended_early
            and new.ends_at >= old.starts_at and new.ends_at < old.ends_at) then
      raise exception 'season_rules_frozen';
    end if;
  end if;
  if old.scoring_version = 'legacy' and new.scoring_version <> 'legacy'
      and exists(select 1 from public.drink_entries where season_id = old.id) then
    raise exception 'season_has_legacy_entries';
  end if;
  return new;
end;
$$;

-- RPCs share the lobby lock. A request queued behind closure may still carry a
-- pre-closure timestamp or season snapshot. Reject its new writes after the lock.
create or replace function public._guard_early_season_write()
returns trigger language plpgsql set search_path = public as $$
declare sid uuid;
begin
  if tg_table_name = 'drink_entry_revisions' then
    select season_id into sid from public.drink_entries where id = new.entry_id;
    if exists (select 1 from public.seasons where id = sid and ended_early) then
      raise exception 'correction_closed';
    end if;
  else
    if exists (select 1 from public.seasons where id = new.season_id and ended_early) then
      raise exception 'scoring_closed';
    end if;
  end if;
  return new;
end;
$$;

do $$
declare table_name text;
begin
  foreach table_name in array array['drink_entries', 'drink_entry_revisions', 'chug_duels',
    'quiz_duels', 'time_duels', 'reaction_duels', 'focus_attempts'] loop
    execute format('drop trigger if exists guard_early_season_write on public.%I', table_name);
    execute format('create trigger guard_early_season_write before insert on public.%I
      for each row execute function public._guard_early_season_write()', table_name);
  end loop;
end $$;

create or replace function public.end_test_season(actor_player uuid, target_lobby uuid, target_season uuid)
returns void language plpgsql set search_path = public as $$
declare creator uuid; season public.seasons%rowtype; cutoff timestamptz; member uuid;
begin
  perform pg_advisory_xact_lock(hashtext(target_lobby::text));
  select player_id into creator from public.lobby_memberships
    where lobby_id = target_lobby order by joined_at, id limit 1;
  if creator is distinct from actor_player or actor_player is null then
    raise exception 'permission_denied';
  end if;
  perform public._require_active_lobby(actor_player, target_lobby);

  select * into season from public.seasons where lobby_id = target_lobby
    order by starts_at desc, id desc limit 1;
  if not found or season.id is distinct from target_season then
    raise exception 'permission_denied';
  end if;
  if not public._focus_is_test(season) then raise exception 'test_season_required'; end if;
  if season.ended_early then return; end if; -- retry after a lost reply

  cutoff := clock_timestamp();
  if cutoff < season.starts_at or cutoff >= season.ends_at then
    raise exception 'season_not_active';
  end if;
  update public.seasons set ends_at = cutoff, ended_early = true
    where id = season.id returning * into season;

  update public.quiz_duels set expires_at = least(expires_at, cutoff)
    where season_id = season.id and status in ('invited','accepted','playing','between');
  update public.time_duels set expires_at = least(expires_at, cutoff)
    where season_id = season.id and status in ('invited','accepted','playing');
  update public.reaction_duels set expires_at = least(expires_at, cutoff)
    where season_id = season.id and status in ('invited','accepted');
  -- This also refreshes Quiz and expires Chug duels at the new season cutoff.
  perform public._time_refresh(season, cutoff);
  perform public._reaction_refresh(season, cutoff);

  update public.focus_attempts set expires_at = least(expires_at, cutoff)
    where season_id = season.id and status = 'running';
  for member in select membership_id from public.focus_attempts
    where season_id = season.id and status = 'running' loop
    perform public._focus_expire(member, season.id, cutoff);
  end loop;
end;
$$;

revoke all on function public._guard_early_season_write(), public.end_test_season(uuid,uuid,uuid)
  from public, anon, authenticated;
grant execute on function public.end_test_season(uuid,uuid,uuid) to service_role;
notify pgrst, 'reload schema';
commit;
