"""Private storage authorization and failure paths without live credentials."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
import uuid
import pytest
import data.db as db
from core.models import Player
from tests.test_profile_photo import picture


@pytest.fixture
def service(monkeypatch):
    client = MagicMock()
    query = client.table.return_value
    for method in ['select', 'eq', 'upsert', 'delete']:
        getattr(query, method).return_value = query
    query.execute.return_value.data = []
    player = Player('owner', 'Owner', 'First', 'Last', 'hash', 'owner@example.test')
    monkeypatch.setattr(db, 'get_client', lambda: client)
    monkeypatch.setattr(db, 'get_player', lambda _: player)
    bucket = MagicMock()
    client.storage.get_bucket.return_value = SimpleNamespace(public=False)
    client.storage.from_.return_value = bucket
    return client, query, bucket, player


def test_owner_save_download_replace_remove(service, monkeypatch):
    client, query, bucket, player = service
    reference = {'path': None}
    monkeypatch.setattr(db, '_profile_picture_row', lambda _: reference['path'])
    def persist(row):
        reference['path'] = row['photo_ref']
        return query
    query.upsert.side_effect = persist
    raw = picture()
    db.save_profile_picture('owner', 'hash', raw)
    first = reference['path']
    assert first.startswith('owner/') and first.endswith('.jpg')
    assert bucket.upload.call_args.args[1] != raw  # normalized JPEG, not original metadata
    bucket.download.return_value = b'authorized bytes'
    assert db.download_profile_picture('owner', 'hash', 'owner') == b'authorized bytes'
    db.save_profile_picture('owner', 'hash', raw)
    assert reference['path'] != first
    bucket.remove.assert_called_with([first])
    current = reference['path']
    db.remove_profile_picture('owner', 'hash')
    bucket.remove.assert_called_with([current])
    assert any(call.args == ('photo_ref', current) for call in query.eq.call_args_list)


def test_outsider_denied_before_reading_storage(service, monkeypatch):
    """Not a friend and no shared lobby: nothing about the picture is read."""
    client, _, bucket, _ = service
    monkeypatch.setattr(db, 'list_friendships', lambda _: [])
    monkeypatch.setattr(db, 'list_co_member_players', lambda _: frozenset({'owner', 'someone-else'}))
    assert db.download_profile_picture('owner', 'hash', 'other') is None
    bucket.download.assert_not_called()
    client.table.assert_not_called()


def test_shared_lobby_allows_the_picture_without_friendship(service, monkeypatch):
    _, _, bucket, _ = service
    monkeypatch.setattr(db, 'list_friendships', lambda _: [])
    monkeypatch.setattr(db, 'list_co_member_players', lambda _: frozenset({'owner', 'other'}))
    monkeypatch.setattr(db, '_profile_picture_row', lambda _: f'other/{uuid.uuid4()}.jpg')
    bucket.download.return_value = b'picture'
    assert db.download_profile_picture('owner', 'hash', 'other') == b'picture'


def test_friend_needs_no_shared_lobby_read(service, monkeypatch):
    _, _, bucket, _ = service
    monkeypatch.setattr(db, 'list_friendships', lambda _: [{'sender_id': 'owner', 'recipient_id': 'other', 'status': 'accepted'}])
    monkeypatch.setattr(db, 'list_co_member_players', lambda _: pytest.fail('friends need no lobby read'))
    monkeypatch.setattr(db, '_profile_picture_row', lambda _: f'other/{uuid.uuid4()}.jpg')
    bucket.download.return_value = b'picture'
    assert db.download_profile_picture('owner', 'hash', 'other') == b'picture'


@pytest.mark.parametrize('status,allowed', [('accepted', True), ('pending', True), ('declined', False)])
def test_friend_status_rechecked_each_download(service, monkeypatch, status, allowed):
    _, query, bucket, _ = service
    monkeypatch.setattr(db, 'list_friendships', lambda _: [{'sender_id': 'owner', 'recipient_id': 'other', 'status': status}])
    monkeypatch.setattr(db, '_profile_picture_row', lambda _: f'other/{uuid.uuid4()}.jpg')
    bucket.download.return_value = b'picture'
    assert db.download_profile_picture('owner', 'hash', 'other') == (b'picture' if allowed else None)


def test_stale_session_and_invalid_upload_never_write(service):
    client, _, bucket, _ = service
    with pytest.raises(ValueError, match='sign-in changed'):
        db.save_profile_picture('owner', 'stale', picture())
    with pytest.raises(ValueError):
        db.save_profile_picture('owner', 'hash', b'invalid')
    client.table.assert_not_called()
    bucket.upload.assert_not_called()


def test_public_bucket_is_rejected(service):
    client, _, bucket, _ = service
    client.storage.get_bucket.return_value.public = True
    with pytest.raises(RuntimeError, match='private'):
        db.save_profile_picture('owner', 'hash', picture())
    bucket.upload.assert_not_called()


def test_upload_or_reference_failure_keeps_old_picture(service, monkeypatch):
    _, query, bucket, _ = service
    old = f'owner/{uuid.uuid4()}.jpg'
    monkeypatch.setattr(db, '_profile_picture_row', lambda _: old)
    bucket.upload.side_effect = RuntimeError('offline')
    with pytest.raises(RuntimeError):
        db.save_profile_picture('owner', 'hash', picture())
    query.upsert.assert_not_called()
    bucket.remove.assert_not_called()
    bucket.upload.side_effect = None
    query.upsert.side_effect = RuntimeError('response lost')
    with pytest.raises(RuntimeError):
        db.save_profile_picture('owner', 'hash', picture())
    bucket.remove.assert_not_called()


def test_wrong_owner_path_cannot_be_read(service, monkeypatch):
    monkeypatch.setattr(db, '_profile_picture_row', lambda _: f'other/{uuid.uuid4()}.jpg')
    with pytest.raises(PermissionError):
        db.download_profile_picture('owner', 'hash', 'owner')
    service[2].download.assert_not_called()


def test_avatar_batch_reads_credentials_friendships_references_and_bucket_once(service,monkeypatch):
    from unittest.mock import Mock
    client,query,bucket,player=service
    monkeypatch.setattr(db,'list_co_member_players',lambda _:frozenset())
    client.table.return_value.in_.return_value=query
    actor=Mock(return_value=player)
    friends=Mock(return_value=[{'sender_id':'owner','recipient_id':'friend','status':'accepted'}])
    monkeypatch.setattr(db,'get_player',actor)
    monkeypatch.setattr(db,'list_friendships',friends)
    path=f'friend/{uuid.uuid4()}.jpg'
    query.execute.return_value.data=[{'player_id':'friend','photo_ref':path}]
    bucket.download.return_value=b'allowed'
    assert db.download_profile_pictures('owner','hash',['friend','outsider','friend'])=={'friend':b'allowed'}
    actor.assert_called_once_with('owner')
    friends.assert_called_once_with('owner')
    client.table.return_value.in_.assert_called_once_with('player_id',['friend'])
    client.storage.get_bucket.assert_called_once()
    # A new request rechecks access, even if the previous one returned bytes.
    friends.return_value=[]
    assert db.download_profile_pictures('owner','hash',['friend'])=={}
    assert actor.call_count==2 and bucket.download.call_count==1


def test_avatar_batch_rejects_stale_credentials_before_storage_access(service,monkeypatch):
    client,query,bucket,_=service
    monkeypatch.setattr(db,'list_friendships',lambda _:[])
    monkeypatch.setattr(db,'list_co_member_players',lambda _:frozenset())
    with pytest.raises(ValueError,match='sign-in changed'):
        db.download_profile_pictures('owner','stale',['owner'])
    client.table.assert_not_called()
    bucket.download.assert_not_called()


def test_orphan_cleanup_keeps_current_and_recent_uploads(service, monkeypatch):
    _, _, bucket, _ = service
    current, abandoned, recent = [f'{uuid.uuid4()}.jpg' for _ in range(3)]
    now = datetime.now(timezone.utc)
    old_time = (now - timedelta(hours=25)).isoformat()
    rows = [{'name': name, 'id': name, 'updated_at': old_time if name != recent else now.isoformat()}
            for name in [current, abandoned, recent]]
    monkeypatch.setattr(db, '_list_photo_folder', lambda b, folder: [{'name': 'owner', 'id': None}] if not folder else rows)
    monkeypatch.setattr(db, '_profile_picture_row', lambda _: f'owner/{current}')
    assert db.cleanup_profile_pictures() == 1
    bucket.remove.assert_not_called()
    assert db.cleanup_profile_pictures(apply=True) == 1
    bucket.remove.assert_called_once_with([f'owner/{abandoned}'])


def test_early_access_check_is_used_instead_of_a_second_check(service, monkeypatch):
    from unittest.mock import Mock
    client, query, bucket, player = service
    client.table.return_value.in_.return_value = query
    actor = Mock(return_value=player)
    friends = Mock(return_value=[{'sender_id': 'owner', 'recipient_id': 'friend', 'status': 'accepted'}])
    monkeypatch.setattr(db, 'get_player', actor)
    monkeypatch.setattr(db, 'list_friendships', friends)
    monkeypatch.setattr(db, 'list_co_member_players', lambda _: frozenset())
    access = db.profile_picture_access('owner', 'hash')
    assert actor.call_count == 1 and friends.call_count == 1
    path = f'friend/{uuid.uuid4()}.jpg'
    query.execute.return_value.data = [{'player_id': 'friend', 'photo_ref': path}]
    bucket.download.return_value = b'allowed'
    assert db.download_profile_pictures('owner', 'hash', ['friend', 'outsider'],
                                        access=access) == {'friend': b'allowed'}
    assert actor.call_count == 1 and friends.call_count == 1, 'no second credential or friendship read'


def test_early_access_check_rejects_a_stale_sign_in(service, monkeypatch):
    monkeypatch.setattr(db, 'list_friendships', lambda _: [])
    with pytest.raises(ValueError, match='sign-in changed'):
        db.profile_picture_access('owner', 'stale')


def test_private_bucket_is_checked_once_per_ten_minutes(service, monkeypatch):
    client, _, _, _ = service
    clock = [1000.0]
    monkeypatch.setattr(db, 'monotonic', lambda: clock[0])
    db._profile_picture_bucket()
    db._profile_picture_bucket()
    assert client.storage.get_bucket.call_count == 1
    clock[0] += db.PRIVATE_BUCKET_RECHECK_SECONDS - 1
    db._profile_picture_bucket()
    assert client.storage.get_bucket.call_count == 1
    clock[0] += 1  # exactly ten minutes after the check: check again
    client.storage.get_bucket.return_value = SimpleNamespace(public=True)
    with pytest.raises(RuntimeError, match='private storage bucket'):
        db._profile_picture_bucket()
    with pytest.raises(RuntimeError, match='private storage bucket'):
        db._profile_picture_bucket()  # a refusal is never remembered as a pass
    assert client.storage.get_bucket.call_count == 3


def test_private_bucket_checks_are_separate_per_bucket(service, monkeypatch):
    client, _, _, _ = service
    db._profile_picture_bucket()
    db._private_photo_bucket()
    assert [call.args[0] for call in client.storage.get_bucket.call_args_list] == [
        db.PROFILE_PICTURE_BUCKET, db.CHECKIN_PHOTO_BUCKET]


def test_membership_names_come_in_one_request_and_only_for_their_lobby(service):
    client, query, _, _ = service
    client.table.return_value.select.return_value.in_.return_value = query
    query.execute.return_value.data = [
        {'id': 'm1', 'lobby_id': 'a', 'player_id': 'p1', 'players': {'display_name': 'Mia'}},
        {'id': 'm2', 'lobby_id': 'other', 'player_id': 'p2', 'players': {'display_name': 'Leo'}},
        {'id': 'm3', 'lobby_id': 'c', 'player_id': 'p3', 'players': None},
    ]
    names = db.list_membership_names([('m1', 'a'), ('m2', 'b'), ('m3', 'c'), ('m1', 'a')])
    assert names == {('m1', 'a'): {'player_id': 'p1', 'display_name': 'Mia'},
                     ('m3', 'c'): {'player_id': 'p3', 'display_name': 'Lobby member'}}
    client.table.return_value.select.return_value.in_.assert_called_once_with('id', ['m1', 'm2', 'm3'])


def test_membership_names_without_pairs_sends_nothing(service):
    client, _, _, _ = service
    assert db.list_membership_names([]) == {}
    client.table.assert_not_called()


def test_membership_names_for_many_lobbies_come_in_batches_of_50(service):
    """A player leading 51+ lobbies used to crash the Lobby page (ValueError)."""
    client, query, _, _ = service
    in_ = client.table.return_value.select.return_value.in_
    in_.return_value = query
    query.execute.side_effect = lambda: SimpleNamespace(data=[
        {'id': i, 'lobby_id': 'a', 'player_id': f'p-{i}', 'players': {'display_name': i}}
        for i in in_.call_args.args[1]])
    names = db.list_membership_names([(f'm{i}', 'a') for i in range(120)])
    assert [len(call.args[1]) for call in in_.call_args_list] == [50, 50, 20]
    assert len(names) == 120 and names[('m119', 'a')]['display_name'] == 'm119'


def test_avatar_batch_includes_lobby_mates_but_not_strangers(service, monkeypatch):
    client, query, bucket, player = service
    client.table.return_value.in_.return_value = query
    monkeypatch.setattr(db, 'list_friendships', lambda _: [])
    monkeypatch.setattr(db, 'list_co_member_players', lambda _: frozenset({'owner', 'mate'}))
    path = f'mate/{uuid.uuid4()}.jpg'
    query.execute.return_value.data = [{'player_id': 'mate', 'photo_ref': path}]
    bucket.download.return_value = b'mate picture'
    assert db.download_profile_pictures('owner', 'hash', ['mate', 'stranger']) == {'mate': b'mate picture'}
    client.table.return_value.in_.assert_called_once_with('player_id', ['mate'])


def test_co_members_come_from_current_memberships_in_one_request(service):
    client, query, _, _ = service
    query.is_.return_value = query
    query.execute.return_value.data = [
        {'lobby_id': 'a', 'lobbies': {'lobby_memberships': [
            {'player_id': 'owner', 'left_at': None}, {'player_id': 'mate', 'left_at': None},
            {'player_id': 'gone', 'left_at': '2026-11-20T10:00:00+00:00'}]}},
        {'lobby_id': 'b', 'lobbies': None}]
    assert db.list_co_member_players('owner') == frozenset({'owner', 'mate'})
    assert client.table.call_count == 1
    query.eq.assert_any_call('player_id', 'owner')
    query.is_.assert_called_once_with('left_at', 'null')
