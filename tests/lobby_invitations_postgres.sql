-- Run only against the disposable database installed by migration_chain.cjs.
do $$
declare
  creator uuid := gen_random_uuid();
  maya uuid := gen_random_uuid();
  leo uuid := gen_random_uuid();
  other_player uuid := gen_random_uuid();
  teams uuid := gen_random_uuid();
  casual uuid := gen_random_uuid();
  maya_invite uuid;
  leo_invite uuid;
  old_membership uuid;
  delivery record;
begin
  insert into players(id, display_name, first_name, last_name, pin_hash, email) values
    (creator, 'lobby-invite-creator', 'Test', 'Player', 'test-hash', 'invite-creator@example.com'),
    (maya, 'lobby-invite-maya', 'Test', 'Player', 'test-hash', 'invite-maya@example.com'),
    (leo, 'lobby-invite-leo', 'Test', 'Player', 'test-hash', 'invite-leo@example.com'),
    (other_player, 'lobby-invite-other', 'Test', 'Player', 'test-hash', 'invite-other@example.com');
  insert into friendships(sender_id, recipient_id, status) values
    (creator, maya, 'accepted'), (leo, creator, 'accepted'), (creator, other_player, 'pending');
  insert into lobbies(id, name, invite_code, game_mode, team_count, team_capacity, team_assignment)
    values (teams, 'Invite teams', 'INVITETEAM', 'team', 2, 1, 'random');
  insert into lobbies(id, name, invite_code) values (casual, 'Invite casual', 'INVITECASUAL');
  insert into lobby_memberships(player_id, lobby_id, joined_at) values
    (creator, teams, now() - interval '2 days'), (creator, casual, now() - interval '2 days');
  insert into seasons(lobby_id, starts_at, ends_at, length_choice) values
    (teams, now() - interval '1 day', now() + interval '6 days', '1_week'),
    (casual, now() - interval '1 day', now() + interval '29 days', '1_month');

  begin
    perform issue_lobby_invitation(maya, teams, creator);
    raise exception 'noncreator could invite';
  exception when raise_exception then
    if sqlerrm <> 'invite_creator_only' then raise; end if;
  end;
  begin
    perform issue_lobby_invitation(creator, teams, other_player);
    raise exception 'pending friend could be invited';
  exception when raise_exception then
    if sqlerrm <> 'invite_friends_only' then raise; end if;
  end;

  select * into delivery from issue_lobby_invitation(creator, teams, maya);
  maya_invite := delivery.invite_id;
  assert delivery.recipient_email = 'invite-maya@example.com';
  assert delivery.inviter_name = 'lobby-invite-creator' and delivery.lobby_name = 'Invite teams';
  assert (select expires_at from lobby_invitations where id = maya_invite)
    = (select ends_at from seasons where lobby_id = teams);
  assert (select count(*) from pending_lobby_invitations(maya)) = 1;
  assert (select count(*) from pending_lobby_invitations(other_player)) = 0;
  assert (select count(*) from lobby_memberships where lobby_id = teams) = 1;

  begin
    perform issue_lobby_invitation(creator, teams, maya);
    raise exception 'duplicate invite saved';
  exception when raise_exception then
    if sqlerrm <> 'invite_pending' then raise; end if;
  end;
  begin
    perform respond_to_lobby_invitation(other_player, maya_invite, 'accept');
    raise exception 'forwarded invitation accepted';
  exception when raise_exception then
    if sqlerrm <> 'invite_unavailable' then raise; end if;
  end;

  select invite_id into leo_invite from issue_lobby_invitation(creator, teams, leo);
  assert respond_to_lobby_invitation(maya, maya_invite, 'accept') = 'Invite teams';
  assert exists(select 1 from lobby_memberships where player_id = maya and lobby_id = teams and team_id is not null);
  begin
    perform respond_to_lobby_invitation(leo, leo_invite, 'accept');
    raise exception 'full lobby accepted another member';
  exception when raise_exception then
    if sqlerrm <> 'lobby_full' then raise; end if;
  end;
  assert exists(select 1 from pending_lobby_invitations(leo));
  assert respond_to_lobby_invitation(leo, leo_invite, 'decline') = 'Invite teams';
  assert not exists(select 1 from lobby_memberships where player_id = leo and lobby_id = teams);
  begin
    perform respond_to_lobby_invitation(leo, leo_invite, 'accept');
    raise exception 'consumed invite accepted';
  exception when raise_exception then
    if sqlerrm <> 'invite_unavailable' then raise; end if;
  end;
  begin
    perform issue_lobby_invitation(creator, teams, leo);
    raise exception 'declined invite was sent again immediately';
  exception when raise_exception then
    if sqlerrm <> 'invite_rate_limited' then raise; end if;
  end;

  -- A departed member's reserved slot is restored even in the full team lobby.
  select id into old_membership from lobby_memberships where lobby_id = teams and player_id = maya;
  update lobby_memberships set left_at = now() where id = old_membership;
  update lobby_invitations set created_at = now() - interval '25 hours' where id = maya_invite;
  select invite_id into maya_invite from issue_lobby_invitation(creator, teams, maya);
  assert respond_to_lobby_invitation(maya, maya_invite, 'accept') = 'Invite teams';
  assert exists(select 1 from lobby_memberships where id = old_membership and left_at is null and team_id is not null);

  -- Going through Join with a code while invited can leave only one membership.
  select invite_id into maya_invite from issue_lobby_invitation(creator, casual, maya);
  assert (select expires_at - created_at from lobby_invitations where id = maya_invite) = interval '7 days';
  insert into lobby_memberships(player_id, lobby_id) values (maya, casual) returning id into old_membership;
  assert respond_to_lobby_invitation(maya, maya_invite, 'accept') = 'Invite casual';
  assert (select id from lobby_memberships where lobby_id = casual and player_id = maya) = old_membership;

  select invite_id into leo_invite from issue_lobby_invitation(creator, casual, leo);
  update lobby_invitations set expires_at = now() where id = leo_invite;
  assert not exists(select 1 from pending_lobby_invitations(leo));
  begin
    perform respond_to_lobby_invitation(leo, leo_invite, 'accept');
    raise exception 'expired invite accepted';
  exception when raise_exception then
    if sqlerrm <> 'invite_unavailable' then raise; end if;
  end;

  update lobby_invitations set created_at = now() - interval '25 hours' where id = leo_invite;
  select invite_id into leo_invite from issue_lobby_invitation(creator, casual, leo);
  assert exists(select 1 from pending_lobby_invitations(leo));
  perform delete_lobby(creator, casual);
  assert not exists(select 1 from pending_lobby_invitations(leo));
  begin
    perform respond_to_lobby_invitation(leo, leo_invite, 'accept');
    raise exception 'deleted lobby accepted an invite';
  exception when raise_exception then
    if sqlerrm <> 'invite_unavailable' then raise; end if;
  end;
end $$;
