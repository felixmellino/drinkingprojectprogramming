-- Requires 025 (and the earlier friendship, team, leave and delete migrations).
begin;

create table public.lobby_invitations (
  id uuid primary key default gen_random_uuid(),
  lobby_id uuid not null references public.lobbies(id),
  inviter_id uuid not null references public.players(id),
  recipient_id uuid not null references public.players(id),
  created_at timestamptz not null,
  expires_at timestamptz not null,
  status text not null default 'pending' check (status in ('pending','accepted','declined','expired')),
  check (inviter_id <> recipient_id)
);
create unique index lobby_invitations_one_pending
  on public.lobby_invitations(lobby_id, recipient_id) where status = 'pending';
create index lobby_invitations_recipient on public.lobby_invitations(recipient_id, created_at)
  where status = 'pending';
create index lobby_invitations_sender_rate on public.lobby_invitations(inviter_id, created_at);

alter table public.lobby_invitations enable row level security;
revoke all on public.lobby_invitations from public, anon, authenticated;
grant select, insert, update on public.lobby_invitations to service_role;

create function public.issue_lobby_invitation(actor_player uuid, target_lobby uuid, target_friend uuid)
returns table (invite_id uuid, recipient_email text, inviter_name text, lobby_name text)
language plpgsql set search_path = public as $$
declare
  owner_membership public.lobby_memberships%rowtype;
  lobby public.lobbies%rowtype;
  deadline timestamptz;
  sent_at timestamptz;
  address text;
  new_invite uuid;
begin
  -- Serialize the sender's daily quota across lobbies, then share the lobby
  -- lock with membership changes and deletion.
  perform pg_advisory_xact_lock(hashtextextended('lobby_invites:' || actor_player::text, 0));
  perform pg_advisory_xact_lock(hashtext(target_lobby::text));
  sent_at := clock_timestamp();
  select * into owner_membership from public.lobby_memberships m
    where m.lobby_id = target_lobby order by m.joined_at, m.id limit 1;
  if owner_membership.player_id is distinct from actor_player or owner_membership.left_at is not null then
    raise exception 'invite_creator_only';
  end if;

  select * into lobby from public.lobbies where id = target_lobby and deleted_at is null;
  select s.ends_at into deadline from public.seasons s where s.lobby_id = target_lobby
    order by s.starts_at desc, s.id desc limit 1;
  if lobby.id is null or deadline is null or deadline <= sent_at then
    raise exception 'invite_lobby_closed';
  end if;
  if actor_player = target_friend or not exists (
    select 1 from public.friendships where pair_low = least(actor_player, target_friend)
      and pair_high = greatest(actor_player, target_friend) and status = 'accepted'
  ) then
    raise exception 'invite_friends_only';
  end if;
  if exists(select 1 from public.lobby_memberships where lobby_id = target_lobby
            and player_id = target_friend and left_at is null) then
    raise exception 'invite_already_member';
  end if;
  select p.email into address from public.players p where p.id = target_friend;
  if nullif(trim(address), '') is null then raise exception 'invite_email_unavailable'; end if;

  update public.lobby_invitations set status = 'expired'
    where lobby_id = target_lobby and recipient_id = target_friend
      and status = 'pending' and expires_at <= sent_at;
  if exists(select 1 from public.lobby_invitations where lobby_id = target_lobby
            and recipient_id = target_friend and status = 'pending') then
    raise exception 'invite_pending';
  end if;
  if (select count(*) from public.lobby_invitations where inviter_id = actor_player
      and created_at > sent_at - interval '24 hours') >= 20
    or exists(select 1 from public.lobby_invitations where lobby_id = target_lobby
      and recipient_id = target_friend and created_at > sent_at - interval '24 hours') then
    raise exception 'invite_rate_limited';
  end if;

  insert into public.lobby_invitations(lobby_id, inviter_id, recipient_id, created_at, expires_at)
    values (target_lobby, actor_player, target_friend, sent_at, least(deadline, sent_at + interval '7 days'))
    returning id into new_invite;
  return query select new_invite, address, p.display_name, lobby.name
    from public.players p where p.id = actor_player;
end;
$$;

create function public.pending_lobby_invitations(actor_player uuid)
returns table (invite_id uuid, lobby_name text, inviter_name text)
language sql stable set search_path = public as $$
  select i.id, l.name, p.display_name
  from public.lobby_invitations i
  join public.lobbies l on l.id = i.lobby_id
  join public.players p on p.id = i.inviter_id
  where i.recipient_id = actor_player and i.status = 'pending'
    and l.deleted_at is null and i.expires_at > statement_timestamp()
  order by i.created_at desc, i.id;
$$;

create function public.respond_to_lobby_invitation(actor_player uuid, target_invite uuid, response text)
returns text language plpgsql set search_path = public as $$
declare
  target_lobby uuid;
  invitation public.lobby_invitations%rowtype;
  member public.lobby_memberships%rowtype;
  at_time timestamptz;
begin
  if response is null or response not in ('accept', 'decline') then
    raise exception 'invalid_invite_response';
  end if;
  select lobby_id into target_lobby from public.lobby_invitations
    where id = target_invite and recipient_id = actor_player;
  if not found then raise exception 'invite_unavailable'; end if;

  perform pg_advisory_xact_lock(hashtext(target_lobby::text));
  at_time := clock_timestamp();
  select * into invitation from public.lobby_invitations where id = target_invite;
  if invitation.status <> 'pending' or invitation.expires_at <= at_time
    or not exists(select 1 from public.lobbies where id = target_lobby and deleted_at is null) then
    raise exception 'invite_unavailable';
  end if;

  if response = 'decline' then
    update public.lobby_invitations set status = 'declined' where id = target_invite;
  else
    select * into member from public.lobby_memberships
      where lobby_id = target_lobby and player_id = actor_player;
    if not found then
      -- The existing membership trigger enforces capacity and team assignment.
      insert into public.lobby_memberships(lobby_id, player_id) values (target_lobby, actor_player);
    elsif member.left_at is not null then
      perform public.rejoin_lobby(actor_player, target_lobby);
    end if;
    update public.lobby_invitations set status = 'accepted' where id = target_invite;
  end if;
  return (select name from public.lobbies where id = target_lobby);
end;
$$;

revoke all on function public.issue_lobby_invitation(uuid,uuid,uuid),
  public.pending_lobby_invitations(uuid), public.respond_to_lobby_invitation(uuid,uuid,text)
  from public, anon, authenticated;
grant execute on function public.issue_lobby_invitation(uuid,uuid,uuid),
  public.pending_lobby_invitations(uuid), public.respond_to_lobby_invitation(uuid,uuid,text)
  to service_role;
notify pgrst, 'reload schema';
commit;
