"""Exercise the menu, saved profile, security and stats through Streamlit."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import pytest
from streamlit.testing.v1 import AppTest
from core.models import Player
from core.auth import hash_password
from core.profile import edit_profile, change_password

ROOT = Path(__file__).resolve().parents[1]


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception
    return at


@pytest.fixture
def repo(monkeypatch):
    # Profile fixtures have no lobby repository; restoration has its own tests.
    monkeypatch.setattr('shared.restore_selection', lambda player_id: None)
    monkeypatch.setattr('data.db.download_profile_picture', lambda *args: None)
    state = {'player': Player('self', 'Mia', 'Mia', 'Silva', hash_password('password8'), 'mia@example.test')}
    monkeypatch.setattr('device_login._browser_storage', lambda **c: {'request_id': c['request_id'], 'token': '', 'available': True})
    monkeypatch.setattr('data.db.get_player', lambda _: state['player'])
    def save(pid, version, first, last, username):
        state['player'] = edit_profile(state['player'], first, last, username, [])
        return state['player']
    monkeypatch.setattr('data.db.update_profile', save)
    def password(pid, version, current, new, confirm):
        state['player'] = change_password(state['player'], current, new, confirm)
        return state['player']
    monkeypatch.setattr('data.db.update_password', password)
    return state


def page(repo):
    at = AppTest.from_file(ROOT / 'pages/1_Profile.py')
    at.session_state['player_id'] = repo['player'].id
    at.session_state['credential_version'] = repo['player'].pin_hash
    return at.run()


def test_menu_edit_and_saved_profile_in_new_session(repo):
    at = page(repo)
    assert not at.exception
    labels = [b.label for b in at.button]
    assert labels[-5:] == ['Edit profile', 'Friends', 'My stats', 'Account & security', 'Log out']
    assert not at.text_input
    click(at, 'Edit profile')
    for field, value in zip(at.text_input, ['NewMia', 'New', 'Name']):
        field.input(value)
    click(at, 'Save changes')
    assert at.success
    assert at.session_state['player_display_name'] == 'NewMia'
    click(at, 'Back to Profile')
    fresh = page(repo)
    click(fresh, 'Edit profile')
    assert [f.value for f in fresh.text_input] == ['NewMia', 'New', 'Name']
    assert repo['player'].id == 'self'


def test_invalid_edit_and_password_change(repo):
    at = page(repo)
    click(at, 'Edit profile')
    at.text_input[0].input(' ')
    click(at, 'Save changes')
    assert at.error and repo['player'].display_name == 'Mia'
    click(at, 'Back to Profile')
    click(at, 'Account & security')
    original = repo['player'].pin_hash
    for field, value in zip(at.text_input, ['wrong', 'newpass8', 'newpass8']):
        field.input(value)
    click(at, 'Change password')
    assert at.error and repo['player'].pin_hash == original
    for field, value in zip(at.text_input, ['password8', 'newpass8', 'newpass8']):
        field.input(value)
    click(at, 'Change password')
    assert 'player_id' not in at.session_state
    assert repo['player'].pin_hash != original
    assert any('Password changed' in s.value for s in at.success)


def stats_text(at):
    from html import unescape
    import re
    return ' '.join(unescape(re.sub('<[^>]+>', ' ', ''.join(m.value for m in at.markdown if '<section class="profile-stats"' in m.value))).split())


def test_stats_finished_lobbies_without_selection_and_fresh_session(repo, monkeypatch):
    from tests.test_scoring_v1 import entry
    now = datetime.now(timezone.utc)
    memberships = [SimpleNamespace(id=f'm{i}', lobby_id=f'l{i}') for i in range(6)]
    monkeypatch.setattr('data.db.list_memberships_for_player', lambda _: memberships)
    def seasons(lid):
        end = now + timedelta(days=1) if lid == 'l5' else now - timedelta(days=1)
        return [SimpleNamespace(id=lid, ends_at=end)]
    monkeypatch.setattr('data.db.list_seasons_for_lobby', seasons)
    def entries(sid):
        assert sid != 'l5', 'Active lobby must not count'
        i = int(sid[1:])
        return [replace(entry(sid, f'm{i}', 'beer', 'small', 0), season_id=sid, points_awarded=11)]
    monkeypatch.setattr('data.db.list_drink_entries', entries)
    at = page(repo)
    click(at, 'My stats')
    text = stats_text(at)
    assert 'Total points 55' in text and 'Drinks 5' in text
    assert 'Lobbies played 5' in text and 'Total Wins 5' in text
    at.session_state['current_lobby_id'] = 'l5'
    at.run()
    assert stats_text(at) == text
    fresh = page(repo)
    click(fresh, 'My stats')
    assert stats_text(fresh) == text


def test_stats_empty_and_load_failure(repo, monkeypatch):
    monkeypatch.setattr('data.db.list_memberships_for_player', lambda _: [])
    at = page(repo)
    click(at, 'My stats')
    assert 'Total points 0' in stats_text(at) and 'Total Wins 0' in stats_text(at)
    assert at.info
    monkeypatch.setattr('data.db.list_memberships_for_player', lambda _: [SimpleNamespace(lobby_id='lobby')])
    monkeypatch.setattr('data.db.list_seasons_for_lobby', lambda _: [])
    at.run()
    assert 'Total points 0' in stats_text(at)
    def unavailable(_):
        raise RuntimeError('offline')
    monkeypatch.setattr('data.db.list_seasons_for_lobby', unavailable)
    at.run()
    assert not at.exception and at.error and not stats_text(at)


def test_save_failure_keeps_form_and_identity(repo, monkeypatch):
    def unavailable(*args):
        raise RuntimeError('offline')
    monkeypatch.setattr('data.db.update_profile', unavailable)
    at = page(repo)
    click(at, 'Edit profile')
    at.text_input[0].input('NewMia')
    click(at, 'Save changes')
    assert at.error
    assert at.text_input[0].value == 'NewMia'
    assert repo['player'].display_name == 'Mia'
    assert at.session_state['player_id'] == 'self'
