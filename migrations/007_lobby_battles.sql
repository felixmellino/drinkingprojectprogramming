-- Recovered for review only; do not apply before scoring-v1 integration review.
-- Apply once after 006_friendships.sql. Back up existing data first. No records are deleted.
-- Server-only aggregate + version: core/lobby_battles.py owns validation;
-- this RPC commits the validated state and relational records together.
begin;
alter table public.lobby_memberships add column is_active boolean not null default true;
create table public.lobby_states (
  lobby_id uuid primary key references public.lobbies(id),
  state jsonb not null,
  version uuid not null default gen_random_uuid()
);
alter table public.lobby_states enable row level security;
revoke all on public.lobby_states from public, anon, authenticated;
grant all on public.lobby_states to service_role;

-- Refuse to guess how to handle legacy groups above the newly agreed limit.
do $$ begin
  if exists (select 1 from public.lobby_memberships group by lobby_id having count(*) > 10) then
    raise exception 'A legacy lobby has more than 10 players. Resolve its capacity with the team before migrating.';
  end if;
end $$;
insert into public.lobby_states(lobby_id, state)
select l.id, jsonb_build_object(
  'id', l.id, 'name', l.name, 'invite_code', l.invite_code,
  'capacity', 10, 'length_choice', coalesce((select length_choice from public.seasons
      where lobby_id=l.id order by starts_at desc limit 1), '1_month'),
  'owner_id', (select player_id from public.lobby_memberships where lobby_id=l.id order by joined_at, id limit 1),
  'closed', not exists(select 1 from public.lobby_memberships where lobby_id=l.id),
  'members', coalesce((select jsonb_agg(jsonb_build_object('id', m.id, 'player_id', m.player_id,
      'active', true, 'blocked', false, 'joined_at', m.joined_at,
      'periods', jsonb_build_array(jsonb_build_object('start', m.joined_at, 'end', null))))
    from public.lobby_memberships m where m.lobby_id=l.id), '[]'::jsonb),
  'invitations', '[]'::jsonb,
  'seasons', coalesce((select jsonb_agg(to_jsonb(s) order by s.starts_at)
    from public.seasons s where s.lobby_id=l.id), '[]'::jsonb)
) from public.lobbies l;

create function public.save_lobby_state(next_state jsonb, expected_version uuid)
returns void language plpgsql set search_path = public as $$
declare
  lid uuid := (next_state->>'id')::uuid;
  actual uuid;
  m jsonb;
  s jsonb;
begin
  -- Also locks creation of the same aggregate; no partial lobby on failures.
  perform pg_advisory_xact_lock(hashtextextended(lid::text, 1));
  select version into actual from lobby_states where lobby_id=lid for update;
  if actual is distinct from expected_version then
    raise exception 'Lobby changed. Refresh and try again.' using errcode='40001';
  end if;
  insert into lobbies(id, name, invite_code)
    values(lid, next_state->>'name', next_state->>'invite_code')
    on conflict(id) do update set name=excluded.name;
  insert into lobby_states(lobby_id, state) values(lid, next_state)
    on conflict(lobby_id) do update set state=excluded.state, version=gen_random_uuid();
  for m in select value from jsonb_array_elements(next_state->'members') loop
    insert into lobby_memberships(id, player_id, lobby_id, joined_at, is_active)
      values((m->>'id')::uuid, (m->>'player_id')::uuid, lid,
             (m->>'joined_at')::timestamptz, (m->>'active')::boolean)
      on conflict(id) do update set is_active=excluded.is_active, joined_at=excluded.joined_at;
  end loop;
  for s in select value from jsonb_array_elements(next_state->'seasons') loop
    insert into seasons(id, lobby_id, starts_at, ends_at, length_choice)
      values((s->>'id')::uuid, lid, (s->>'starts_at')::timestamptz,
             (s->>'ends_at')::timestamptz, s->>'length_choice')
      on conflict(id) do nothing;
  end loop;
end;
$$;
revoke all on function public.save_lobby_state(jsonb, uuid) from public, anon, authenticated;
grant execute on function public.save_lobby_state(jsonb, uuid) to service_role;

-- Reject stale sessions and expiry races at the actual write. Locking the
-- aggregate row serializes a check-in against a simultaneous leave/removal.
create function public.guard_battle_entry() returns trigger
language plpgsql set search_path=public as $$
declare lid uuid; active boolean; start_at timestamptz; end_at timestamptz; closed boolean;
begin
  select lobby_id into lid from lobby_memberships where id=new.membership_id;
  select (state->>'closed')::boolean into closed from lobby_states where lobby_id=lid for update;
  select is_active into active from lobby_memberships where id=new.membership_id;
  select starts_at, ends_at into start_at, end_at from seasons
    where id=new.season_id and lobby_id=lid;
  if active is distinct from true or closed is distinct from false
     or start_at is null or clock_timestamp() < start_at or clock_timestamp() >= end_at
     or new.submitted_at < start_at or new.submitted_at >= end_at then
    raise exception 'Choose a current membership and an active battle.' using errcode='42501';
  end if;
  if not ((new.submitted_at at time zone 'Europe/Lisbon')::date
        = (clock_timestamp() at time zone 'Europe/Lisbon')::date)
     or extract(isodow from clock_timestamp() at time zone 'Europe/Lisbon') not between 4 and 7
     or (extract(isodow from clock_timestamp() at time zone 'Europe/Lisbon')=4
         and (clock_timestamp() at time zone 'Europe/Lisbon')::time < time '12:00') then
    raise exception 'Check-ins are open Thursday noon through Sunday in Lisbon.' using errcode='42501';
  end if;
  return new;
end;
$$;
create trigger drink_entries_active_battle before insert on public.drink_entries
  for each row execute function public.guard_battle_entry();
revoke all on function public.guard_battle_entry() from public, anon, authenticated;
commit;
