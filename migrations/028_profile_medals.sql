-- Apply at the medal feed rollout to save its announcement cutoff.
begin;

create table if not exists public.profile_medal_rollout (
  singleton boolean primary key default true check (singleton),
  launched_at timestamptz not null default now()
);
alter table public.profile_medal_rollout enable row level security;
revoke all on public.profile_medal_rollout from public, anon, authenticated;
grant select on public.profile_medal_rollout to service_role;

-- Reapplying the migration must preserve the original feed cutoff.
insert into public.profile_medal_rollout default values on conflict do nothing;

commit;
