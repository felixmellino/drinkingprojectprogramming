"""Fewer page reads must preserve fresh credentials and membership checks."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import data.db as db
from core.models import Player, LobbyMembership
from tests.test_scoring_v1 import season


@pytest.fixture
def auth(monkeypatch):
    player = Player('player', 'Mia', 'Mia', 'S', 'version', 'private@example.test')
    reader = Mock(return_value=player)
    monkeypatch.setattr(db, 'get_player', reader)
    monkeypatch.setattr('shared.sync_storage', lambda: '')
    monkeypatch.setattr('shared.ask_for_location', lambda: None)
    monkeypatch.setattr('shared.bottom_navigation', lambda: None)
    monkeypatch.setattr('shared.show_accounts', lambda: st.info('Signed out'))
    return player, reader


def open_page(script, player):
    page = AppTest.from_string('import streamlit as st\n' + script)
    for key, value in dict(player_id=player.id, credential_version=player.pin_hash,
            current_membership_id='member', current_lobby_id='lobby', current_season_id='season').items():
        page.session_state[key] = value
    return page.run()


def test_navigation_action_does_not_wait_for_current_pages_account_read(auth, monkeypatch):
    player, reader = auth
    def navigation():
        if st.button('Switch page'):
            st.stop()  # st.switch_page ends this run before the destination starts.
    monkeypatch.setattr('shared.bottom_navigation', navigation)
    page = open_page('from shared import require_login\nrequire_login()\nst.success("Private page")', player)
    assert reader.call_count == 1
    page.button[0].click().run()
    assert not page.exception and reader.call_count == 1


def test_account_read_reused_only_after_fresh_validation_and_revocation_stops_render(auth):
    player, reader = auth
    script = 'from shared import require_login, authenticated_player\nrequire_login()\nst.success(authenticated_player().display_name)'
    page = open_page(script, player)
    assert not page.exception and reader.call_count == 1 and page.success[0].value == 'Mia'
    reader.return_value = Player('player', 'Mia', 'Mia', 'S', 'changed-password', player.email)
    page.run()
    assert not page.exception and reader.call_count == 2
    assert not page.success and any('Signed out' in x.value for x in page.info)
    assert '_validated_player' not in page.session_state


@pytest.mark.parametrize('member_ok,season_ok,allowed', [(True, True, True), (False, False, False), (True, False, False)])
def test_selected_context_reads_once_and_rejects_revoked_or_foreign_access(auth, monkeypatch, member_ok, season_ok, allowed):
    player, _ = auth
    member = LobbyMembership('member', 'player', 'lobby', datetime.now(timezone.utc))
    reader = Mock(return_value=(member if member_ok else None, season() if season_ok else None))
    monkeypatch.setattr(db, 'membership_context', reader)
    duplicate = Mock(side_effect=AssertionError('Validated season must not be read twice'))
    monkeypatch.setattr(db, 'list_seasons_for_lobby', duplicate)
    script = '''from shared import require_login, require_active_membership, selected_season
require_login()
m,l,s = require_active_membership()
st.success(selected_season(l,s).id)
'''
    page = open_page(script, player)
    assert not page.exception
    reader.assert_called_once_with('player', 'member', 'lobby', 'season')
    assert bool(page.success) is allowed
    assert bool(page.error) is not allowed
    duplicate.assert_not_called()


def test_membership_query_scopes_actor_member_lobby_and_embedded_season(monkeypatch):
    game = season()
    row = dict(id='member', player_id='player', lobby_id='lobby', joined_at=game.starts_at.isoformat(), team_id='team',
        lobbies={'seasons':[dict(id=game.id, lobby_id=game.lobby_id, starts_at=game.starts_at.isoformat(),
            ends_at=game.ends_at.isoformat(), length_choice=game.length_choice)]})
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.execute.return_value = SimpleNamespace(data=[row])
    client = Mock()
    client.table.return_value = query
    monkeypatch.setattr(db, 'get_client', lambda: client)
    member, selected = db.membership_context('player', 'member', 'lobby', 'season')
    assert member.team_id == 'team' and selected.id == 'season'
    assert [c.args for c in query.eq.call_args_list] == [('id','member'),('player_id','player'),('lobby_id','lobby')]
    query.execute.assert_called_once()
    assert db.membership_context('player', 'member', 'lobby', 'foreign-season')[1] is None
    query.execute.return_value = SimpleNamespace(data=[])
    assert db.membership_context('stranger', 'member', 'lobby', 'season') == (None, None)
