"""Recovery instructions must be possible under the actual current game rules."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from unittest.mock import Mock

import pytest
from httpx import ReadTimeout
from postgrest.exceptions import APIError
from streamlit.testing.v1 import AppTest

import data.db as db
from core.action_feedback import duel_closed_message
from core.scoring_v1 import new_rules
from tests.feedback_helpers import assert_blocked
from tests.test_chug_duel_ui import service, open_quiz  # noqa: F401
from tests.test_scoring_ui import ui, open_checkin, set_location, button  # noqa: F401
from tests.test_scoring_v1 import season
from tests.test_checkins import TERRITORY


@pytest.mark.parametrize('available', [0, 1, 2])
def test_quiz_below_minimum_gives_an_attainable_solution(service, monkeypatch, available):
    page, invite = open_quiz(service, monkeypatch, available_points=available)
    button(page, 'Challenge').click().run()
    text = ' '.join(item.value for item in page.error)
    assert not page.exception
    assert 'at least 3' in text and f'you have {available}' in text
    assert 'Earn more' in text and 'lower stake' not in text
    invite.assert_not_called()


def test_qa_opening_uses_season_start_for_every_duel():
    start = datetime(2026, 11, 23, 8, tzinfo=timezone.utc)
    game = replace(season(), starts_at=start, ends_at=start + timedelta(days=7), scoring_rules=new_rules(test_mode=True))
    text = duel_closed_message(game, now=start - timedelta(days=1))
    assert 'Mon 23 Nov at 08:00' in text and game.timezone_name in text


@pytest.mark.parametrize('module', ['core.chug_duel', 'core.quiz_duel', 'core.time_duel'])
def test_role_limit_never_promises_that_finishing_restores_the_allowance(module):
    from importlib import import_module
    errors = import_module(module).ERRORS
    text = next(value for key, value in errors.items() if key.endswith('_limit'))
    assert 'before it starts' in text and 'Once started' in text
    assert 'finishing the duel does not reset' in text and '06:00' in text


def test_accurate_gps_in_overlapping_territories_is_not_reported_as_poor_accuracy(ui, monkeypatch):
    state, _ = ui
    monkeypatch.setattr('shared.get_territories', lambda: [TERRITORY, replace(TERRITORY, id='overlap')])
    page = open_checkin()
    set_location(page, state, accuracy_m=10)
    assert_blocked(page, 'Submit', 'more than one game territory', 'boundary', 'app organizer')
    assert state['calls'] == 0 and state['entries'] == []


def test_missing_photo_storage_does_not_tell_player_to_repeat_an_impossible_save(ui, monkeypatch):
    state, _ = ui
    save = Mock(side_effect=RuntimeError('Check-in photos require a private storage bucket.'))
    monkeypatch.setattr(db, 'save_drink_entry_photo', save)
    page = open_checkin()
    set_location(page, state)
    capture = page.session_state['checkin_capture'][1]
    button(page, 'Submit').click().run()
    assert not page.exception and 'setup is incomplete' in page.error[0].value
    assert 'app organizer' in page.error[0].value
    assert 'storage bucket' not in page.error[0].value
    assert any('private storage bucket' in item.value for item in page.markdown)
    assert page.session_state['checkin_capture'][1] == capture
    assert state['entries'] == []


def test_logout_network_failure_retains_session_for_a_safe_retry(monkeypatch):
    revoke = Mock(side_effect=ReadTimeout('private provider details'))
    monkeypatch.setattr(db, 'revoke_remembered_session', revoke)
    page = AppTest.from_string('''
import streamlit as st
from device_login import log_out
if st.session_state.get('player_id'):
    if st.button('Log out'):
        log_out()
else:
    st.info('Signed out')
''')
    page.session_state['player_id'] = 'local-player'
    page.session_state['_device_token'] = 'synthetic-device-token'
    page.run()
    assert_blocked(page, 'Log out', 'still signed in', 'connection', 'Log out again')
    assert page.session_state['player_id'] == 'local-player'
    assert page.session_state['_device_token'] == 'synthetic-device-token'
    revoke.side_effect = None
    button(page, 'Log out').click().run()
    assert not page.exception and 'player_id' not in page.session_state
    assert page.session_state['_device_command']['action'] == 'clear'
    assert revoke.call_count == 2


def test_lobby_invitation_sql_rejections_all_have_recovery_messages():
    from lobby_invite_ui import SEND_ERRORS, RESPONSE_ERRORS
    sql = (Path(__file__).resolve().parents[1] / 'migrations/026_lobby_invitations.sql').read_text(encoding='utf-8')
    reasons = set(re.findall(r"raise exception '([a-z_]+)'", sql))
    assert reasons <= SEND_ERRORS.keys() | RESPONSE_ERRORS.keys()
    assert '20' in SEND_ERRORS['invite_rate_limited'] and '24 hours' in SEND_ERRORS['invite_rate_limited']
    assert 'invite code' in SEND_ERRORS['invite_email_unavailable']


def test_lobby_invitation_rejection_popup_keeps_pending_invite_and_never_reports_success(monkeypatch):
    import lobby_invite_ui as invites
    monkeypatch.setattr(invites, '_session_is_current', lambda _: True)
    action = Mock(side_effect=APIError({'message': 'invalid_invite_response', 'code': 'P0001'}))
    monkeypatch.setattr(db, 'respond_to_lobby_invitation', action)
    page = AppTest.from_string('''
import streamlit as st
from lobby_invite_ui import _respond
st.text('Pending invite remains here')
if st.button('Accept'):
    _respond('player', 'invite', 'accept')
''').run()
    assert_blocked(page, 'Accept', 'response could not be accepted', 'Accept or Decline')
    assert not page.success and action.call_count == 1


def test_unexpected_service_errors_do_not_expose_backend_details():
    page = AppTest.from_string('''
from action_feedback import service_error
service_error(RuntimeError('private provider details'), 'Connection failed. Reopen this page to retry.')
''').run()
    assert not page.exception
    assert page.error[0].value == 'Connection failed. Reopen this page to retry.'
    assert not page.expander


def test_ended_season_does_not_suggest_an_unavailable_season_picker(ui):
    state, game = ui
    state['now'] = game.ends_at + timedelta(seconds=1)
    page = open_checkin()
    text = ' '.join(item.value for item in page.markdown)
    assert not page.exception and 'Season over' in text
    assert 'Create or join a new lobby' in text and 'make it current' in text
    assert 'choose a new season' not in text


def test_season_closure_takes_priority_over_a_cooldown_before_opening_camera(ui):
    state, game = ui
    from tests.test_scoring_v1 import entry
    state['entries'] = [entry('recent', 'member', 'beer', 'small', 0)]
    game.ends_at = state['now'] + timedelta(seconds=30)
    state['now'] += timedelta(seconds=31)
    page = open_checkin()
    text = ' '.join(item.value for item in page.markdown)
    assert not page.exception and 'Season over' in text
    assert 'Next check-in in' not in text


def test_future_season_warning_uses_lobby_timezone_after_capture(ui):
    state, game = ui
    page = open_checkin()
    game.starts_at = state['now'] + timedelta(days=1)
    game.timezone_name = 'America/New_York'
    page.run()
    assert not page.exception
    assert any('13:00:00 EST' in item.value and 'America/New_York' in item.value for item in page.warning)
