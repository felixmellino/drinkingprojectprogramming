-- WeGoPub database schema (Supabase / Postgres).
-- Run once against your Supabase project's SQL editor.

create extension if not exists pgcrypto;

create table players (
  id uuid primary key default gen_random_uuid(),
  display_name text unique not null,
  first_name text not null,
  last_name text not null,
  pin_hash text not null
);

create table lobbies (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  invite_code text unique not null
);

create table lobby_memberships (
  id uuid primary key default gen_random_uuid(),
  player_id uuid not null references players(id),
  lobby_id uuid not null references lobbies(id),
  joined_at timestamptz not null default now(),
  unique (player_id, lobby_id)
);

create table seasons (
  id uuid primary key default gen_random_uuid(),
  lobby_id uuid not null references lobbies(id),
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  length_choice text not null
);

-- GeoJSON Polygon, e.g. {"type":"Polygon","coordinates":[[[lng,lat],...]]}
create table territories (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  boundary jsonb not null
);

create table drink_entries (
  id uuid primary key default gen_random_uuid(),
  membership_id uuid not null references lobby_memberships(id),
  season_id uuid not null references seasons(id),
  drink_type text not null,
  amount double precision,
  photo_ref text not null,
  device_gps_lat double precision,
  device_gps_lng double precision,
  photo_gps_lat double precision,
  photo_gps_lng double precision,
  territory_id uuid references territories(id),
  location_check_result text not null,
  points_awarded integer not null,
  submitted_at timestamptz not null
);

create index drink_entries_duplicate_check
  on drink_entries (membership_id, drink_type, submitted_at);
create index drink_entries_season on drink_entries (season_id);
create index drink_entries_territory on drink_entries (territory_id);

-- GeoJSON Point, e.g. {"type":"Point","coordinates":[lng,lat]}
create table arenas (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  map_point jsonb not null
);

create table minigame_attempts (
  id uuid primary key default gen_random_uuid(),
  membership_id uuid not null references lobby_memberships(id),
  season_id uuid not null references seasons(id),
  arena_id uuid not null references arenas(id),
  game_type text not null,
  game_window_id text not null,
  started_at timestamptz not null,
  status text not null,
  result text
);

create index minigame_attempts_window
  on minigame_attempts (membership_id, game_window_id);
