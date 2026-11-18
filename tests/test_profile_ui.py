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


def test_stats_no_lobby_and_current_season(repo, monkeypatch):
    at = page(repo)
    click(at, 'My stats')
    assert any('Choose a lobby' in msg.value for msg in at.info)
    now = datetime.now(timezone.utc)
    monkeypatch.setattr('data.db.list_memberships_for_player', lambda _: [SimpleNamespace(id='member', lobby_id='lobby')])
    current = SimpleNamespace(id='current', starts_at=now-timedelta(days=1), ends_at=now+timedelta(days=1))
    monkeypatch.setattr('data.db.list_seasons_for_lobby', lambda _: [current])
    from tests.test_scoring_v1 import entry
    from tests.test_checkins import TERRITORY
    entries = [entry('one', 'member', 'beer', 'large', 0)]
    monkeypatch.setattr('data.db.list_drink_entries', lambda sid: entries if sid == 'current' else pytest.fail('Wrong season'))
    monkeypatch.setattr('profile_ui.get_territories', lambda: [TERRITORY])
    at.session_state['current_lobby_id'] = 'lobby'
    at.session_state['current_season_id'] = 'old'
    at.run()
    assert not at.exception
    assert [m.value for m in at.metric] == ['3', '#1', '1']
    entries.clear()
    at.run()
    assert [m.value for m in at.metric] == ['0', 'Unranked', '0']
    monkeypatch.setattr('profile_ui.get_territories', lambda: (_ for _ in ()).throw(RuntimeError('offline')))
    at.run()
    assert at.metric[2].value == 'Unavailable'


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
