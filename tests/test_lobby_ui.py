from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as Obj
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

import data.db as db
from core.lobbies import create_season
from core.models import Lobby, LobbyMembership
from tests.test_scoring_v1 import entry

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def ui(monkeypatch):
    now = datetime.now(timezone.utc)
    lobbies = [Lobby('old', 'Older lobby', 'OLDER'), Lobby('new', 'Newest lobby', 'NEWEST'),
               Lobby('past', 'Finished lobby', 'PAST'), Lobby('secret', 'Not joined', 'PRIVATE')]
    members = [LobbyMembership('m-' + l.id, 'me', l.id, now) for l in lobbies[:3]]
    seasons = {l.id: [create_season(l.id, '1_week', now - timedelta(days=offset))]
               for l, offset in zip(lobbies, [2, 1, 10, 0])}
    state = dict(lobbies=lobbies, members=members, seasons=seasons, entries=[], names={})
    monkeypatch.setattr('shared.require_login', lambda: 'me')
    monkeypatch.setattr('shared.show_logged_in_as', lambda: None)
    monkeypatch.setattr(db, 'list_memberships_for_player', lambda _: state['members'])
    monkeypatch.setattr(db, 'list_lobbies', lambda: state['lobbies'])
    monkeypatch.setattr(db, 'list_seasons_for_lobby', lambda lid: state['seasons'].get(lid, []))
    monkeypatch.setattr(db, 'list_drink_entries', lambda _: state['entries'])
    monkeypatch.setattr(db, 'membership_display_name', lambda mid, lid: state['names'].get(mid, mid))
    monkeypatch.setattr(db, 'list_memberships_for_lobby', lambda lid: [Obj(id='leo', player_id='leo-id')])
    state['picture'] = Mock(return_value=None)
    monkeypatch.setattr('lobby_ui.load_picture', state['picture'])
    return state


def page():
    return AppTest.from_file(ROOT / 'pages/2_Lobby.py', default_timeout=10).run()


def cards(at):
    return [item.value for item in at.markdown if '<article class="lobby-card' in item.value]


def click(at, label):
    return next(b for b in at.button if b.label == label).click().run()


def test_joined_lobbies_visible_newest_first_auto_selected_with_no_dropdown(ui):
    at = page()
    assert not at.exception
    shown = cards(at)
    assert 'Newest lobby' in shown[0] and 'Older lobby' in shown[1]
    assert 'lobby-past' in shown[2] and 'Finished lobby' in shown[2]
    assert 'Finished ' in shown[2] and ' left ' in shown[0]
    assert 'No Leader' in shown[2]
    assert all('Not joined' not in s and 'PRIVATE' not in s for s in shown)
    assert at.session_state['current_lobby_id'] == 'new'
    assert at.session_state['current_membership_id'] == 'm-new'
    assert at.session_state['current_season_id'] == ui['seasons']['new'][0].id
    assert not any(s.label in ('Your lobbies', 'View season') for s in at.selectbox)
    assert any(b.label == 'Create a lobby' for b in at.button)
    assert any(b.label == 'Join with a code' for b in at.button)
    assert not any(b.label == 'Start next scoring season' for b in at.button)


def test_leader_uses_existing_tie_rule_public_name_and_private_photo_fallback(ui):
    ui['entries'] = [entry('late', 'mia', 'shot', None, 1, territory=None),
                     entry('early', 'leo', 'shot', None, 0, territory=None)]
    ui['names'] = {'mia': 'Mia', 'leo': 'Leo'}
    at = page()
    assert not at.exception
    assert 'Leader: <strong>Leo</strong>' in cards(at)[0]
    assert 'Winner: <strong>Leo</strong>' in cards(at)[2]
    assert 'lobby-avatar' in cards(at)[0] and '>LE</span>' in cards(at)[0]
    assert 'data:image' not in cards(at)[0]
    assert ui['picture'].call_args.args == ('me', 'leo-id')
    ui['picture'].return_value = b'synthetic-picture'
    at.run()
    assert 'data:image/jpeg;base64,' in cards(at)[0]


def test_finish_refresh_moves_card_and_selects_next_running_lobby(ui):
    at = page()
    ui['seasons']['new'][0].ends_at = datetime.now(timezone.utc)
    at.run()
    assert not at.exception
    assert at.session_state['current_lobby_id'] == 'old'
    assert 'Newest lobby' in next(s for s in cards(at) if 'lobby-past' in s)
    ui['seasons']['old'][0].ends_at = datetime.now(timezone.utc)
    at.run()
    assert not at.exception
    assert 'current_lobby_id' not in at.session_state


def test_service_failure_is_not_displayed_as_no_leader(ui, monkeypatch):
    def fail(_):
        raise RuntimeError('offline')
    monkeypatch.setattr(db, 'list_drink_entries', fail)
    at = page()
    assert not at.exception
    assert all('Standings unavailable' in s and 'No Leader' not in s for s in cards(at))


def test_photo_failure_preserves_leader_and_escaped_text(ui):
    ui['entries'] = [entry('one', 'leo', 'shot', None, 0, territory=None)]
    payload = '<img src=x onerror="alert(1)">'
    ui['names']['leo'] = payload
    ui['lobbies'][1].name = payload
    ui['picture'].side_effect = RuntimeError('offline')
    at = page()
    assert not at.exception
    assert payload not in ''.join(cards(at)) and '&lt;img' in cards(at)[0]
    assert 'Standings unavailable' not in cards(at)[0]


def test_removed_membership_disappears_after_refresh(ui):
    at = page()
    ui['members'] = [m for m in ui['members'] if m.lobby_id != 'new']
    at.run()
    assert not at.exception
    assert all('Newest lobby' not in s for s in cards(at))
    assert at.session_state['current_lobby_id'] == 'old'


def test_join_invalid_code_keeps_lists_and_saves_nothing(ui, monkeypatch):
    save = Mock()
    monkeypatch.setattr(db, 'insert_membership', save)
    at = page()
    at.button(key='open_join_lobby').click().run()
    next(v for v in at.text_input if v.label == 'Invite code').input('badcode')
    click(at, 'Join lobby')
    assert not at.exception and any("doesn't match" in e.value for e in at.error)
    assert len(cards(at)) == 3
    save.assert_not_called()


def test_opening_a_card_selects_its_membership_and_navigates(ui, monkeypatch):
    nav = Mock()
    monkeypatch.setattr('lobby_ui.st.switch_page', nav)
    at = page()
    next(b for b in at.button if b.key == 'open_lobby_old').click().run()
    assert not at.exception
    assert at.session_state['current_lobby_id'] == 'old'
    nav.assert_called_once_with('pages/4_Standings.py')


def test_past_only_and_incomplete_setup_have_no_invented_active_lobby(ui):
    ui['members'] = ui['members'][2:]
    at = page()
    assert not at.exception and len(cards(at)) == 1
    assert 'current_lobby_id' not in at.session_state
    ui['seasons']['past'] = []
    at.run()
    assert not at.exception and 'Setup incomplete' in cards(at)[0]
    assert any(b.label == 'Start lobby' for b in at.button)


def test_last_membership_removed_clears_selection(ui):
    at = page()
    ui['members'] = []
    at.run()
    assert not at.exception and not cards(at)
    assert 'current_lobby_id' not in at.session_state


def test_joining_valid_code_updates_the_visible_list_once(ui, monkeypatch):
    save = Mock(side_effect=ui['members'].append)
    monkeypatch.setattr(db, 'insert_membership', save)
    at = page()
    at.button(key='open_join_lobby').click().run()
    next(v for v in at.text_input if v.label == 'Invite code').input('private')
    click(at, 'Join lobby')
    assert not at.exception
    assert any('Not joined' in s for s in cards(at))
    assert at.session_state['current_lobby_id'] == 'secret'
    assert save.call_count == 1
    at.button(key='open_join_lobby').click().run()
    next(v for v in at.text_input if v.label == 'Invite code').input('private')
    click(at, 'Join lobby')
    assert not at.exception and save.call_count == 1


def test_top_actions_open_separate_dialogs_and_hide_forms_until_clicked(ui):
    at = page()
    assert not at.exception and not at.tabs and not at.text_input
    assert [button.key for button in at.button[:2]] == ['open_create_lobby', 'open_join_lobby']
    at.button(key='open_create_lobby').click().run()
    assert not at.exception
    assert any(field.label == 'Lobby name' for field in at.text_input)
    assert not any(field.label == 'Invite code' for field in at.text_input)
    at.session_state['_lobby_dialog'] = 'join'
    at.run()
    assert not at.exception
    assert any(field.label == 'Invite code' for field in at.text_input)
    assert not any(field.label == 'Lobby name' for field in at.text_input)
