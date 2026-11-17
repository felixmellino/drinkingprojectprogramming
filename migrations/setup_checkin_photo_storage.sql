-- Run after schema.sql on the Supabase project used by the app.
begin;

alter table public.drink_entries add column if not exists photo_captured_at timestamptz;

insert into storage.buckets (id, name, public)
values ('check-in-photos', 'check-in-photos', false)
on conflict (id) do nothing;

do $$
begin
  if exists (select 1 from storage.buckets where id = 'check-in-photos' and public is distinct from false) then
    raise exception 'The existing check-in-photos bucket must be private.';
  end if;
end;
$$;

commit;
