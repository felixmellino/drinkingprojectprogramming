-- Requires 028. Remembers which players have finished a season's recap (R-S03).
-- One row per player and season; the server checks membership and that the season
-- has ended before writing. The row grants nothing: it only hides the banner.
begin;
create table public.season_recap_views (
  player_id uuid not null references public.players(id) on delete cascade,
  season_id uuid not null references public.seasons(id) on delete cascade,
  finished_at timestamptz not null default now(),
  primary key (player_id, season_id)
);
alter table public.season_recap_views enable row level security;
revoke all on public.season_recap_views from public, anon, authenticated;
grant all on public.season_recap_views to service_role;
commit;
