"""Rejected taps explain recovery and never call a mutation."""
from unittest.mock import Mock
from pathlib import Path
import re

import pytest
from streamlit.testing.v1 import AppTest

import data.db as db
from core.checkins import CheckinRejected
from postgrest.exceptions import APIError
from tests.feedback_helpers import assert_blocked
from tests.test_scoring_ui import ui, open_checkin, set_location, button, radio  # noqa: F401


@pytest.mark.parametrize("problem, words", [
    ("off", ("off", "Profile", "turn it on")),
    ("denied", ("blocked", "browser settings", "location services")),
    ("unavailable", ("cannot find", "outside", "try again")),
    ("timeout", ("too long", "off and on")),
    ("unsupported", ("cannot share", "HTTPS", "browser")),
    ("invalid", ("could not be used", "Reload")),
])
def test_location_failures_show_specific_recovery_and_preserve_form(ui, problem, words):
    state, _ = ui
    page = open_checkin()
    radio(page, "Drink").set_value("wine").run()
    capture = page.session_state["checkin_capture"][1]
    state["location"] = {"error": problem}
    page.run()
    assert not page.error  # No popup before the player tries the action.
    assert_blocked(page, "Submit", *words)
    assert state["calls"] == 0 and state["entries"] == []
    assert page.session_state["checkin_capture"][1] == capture
    assert radio(page, "Drink").value == "wine"
    set_location(page, state)
    button(page, "Submit").click().run()
    assert not page.exception and state["calls"] == 1


@pytest.mark.parametrize("reason, words", [
    ("team_required", ("team", "Lobby")),
    ("invalid_selection", ("drink", "listed sizes")),
    ("invalid_photo", ("Retake photo", "fresh")),
    ("invalid_territory", ("territory", "Refresh")),
    ("cooldown", ("two-minute", "wait")),
    ("unexpected_internal_code", ("could not be accepted", "Refresh")),
])
def test_server_rejection_has_recovery_without_exposing_reason_codes(ui, monkeypatch, reason, words):
    state, _ = ui
    save = Mock(side_effect=CheckinRejected(reason))
    monkeypatch.setattr(db, "save_drink_entry_photo", save)
    page = open_checkin()
    set_location(page, state)
    capture = page.session_state["checkin_capture"][1]
    button(page, "Submit").click().run()
    assert not page.exception and save.call_count == 1
    text = " ".join(item.value for item in page.error)
    for word in words:
        assert word in text
    assert text != reason
    if "_" in reason:
        assert reason not in text
    assert page.session_state["checkin_capture"][1] == capture
    assert not state["entries"]


def test_all_blockers_are_shown_and_details_are_optional(monkeypatch):
    mutation = Mock()
    monkeypatch.setattr(db, "insert_lobby", mutation)
    page = AppTest.from_string('''
from action_feedback import action_button
import data.db as db
if action_button("Go", problems=["Choose a player.", None, "Choose a lower stake."], details="Reserved points cannot be reused."):
    db.insert_lobby(None)
''').run()
    assert not page.error
    button(page, "Go").click().run()
    assert not page.exception and len(page.error) == 2
    assert page.expander[0].label == "Details"
    mutation.assert_not_called()


def test_recent_history_failure_explains_why_camera_cannot_open(ui, monkeypatch):
    history = Mock(side_effect=RuntimeError("Service unavailable"))
    camera = Mock()
    monkeypatch.setattr(db, "list_drink_entries_for_membership", history)
    monkeypatch.setattr("camera_capture.camera_photo", camera)
    page = open_checkin()
    assert not page.exception
    assert "cooldown" in page.error[0].value and "Reload Check in" in page.error[0].value
    camera.assert_not_called()


@pytest.mark.parametrize('reason', [
    'location_unavailable', 'location_uncertain', 'duel_entry_locked',
    'scoring_version_mismatch', 'season_has_legacy_entries', 'season_rules_frozen',
    'entry_identity_frozen', 'invalid_timezone',
])
def test_scoring_rpc_preserves_known_rejection_reason_for_specific_ui_feedback(monkeypatch, reason):
    client = Mock()
    client.rpc.return_value.execute.side_effect = APIError({'message': reason, 'code': 'P0001', 'details': None, 'hint': None})
    monkeypatch.setattr(db, 'get_client', lambda: client)
    with pytest.raises(CheckinRejected) as rejected:
        db._scoring_rpc('accept_scoring_checkin', {})
    assert rejected.value.reason == reason


@pytest.mark.parametrize('migration, rpc, prefix', [
    ('011_chug_duel.sql', db._duel_rpc, 'duel_'),
    ('016_quiz_duel.sql', db._quiz_rpc, 'quiz_'),
    ('017_time_duel.sql', db._time_rpc, 'time_'),
    ('025_reaction_duel.sql', db._reaction_rpc, 'reaction_'),
])
def test_sql_duel_rejections_have_a_translation_in_the_rpc_boundary(monkeypatch, migration, rpc, prefix):
    """A new SQL rejection must not fall through as an unexplained API failure."""
    sql = (Path(__file__).resolve().parents[1] / 'migrations' / migration).read_text(encoding='utf-8')
    reasons = set(re.findall(r"raise exception '([a-z_]+)'", sql))
    reasons = {reason for reason in reasons if reason.startswith(prefix) or reason in {
        'permission_denied', 'scoring_closed', 'scoring_setup_required', 'invalid_photo',
    }}
    client = Mock()
    monkeypatch.setattr(db, 'get_client', lambda: client)
    for reason in reasons:
        client.rpc.return_value.execute.side_effect = APIError({'message': reason, 'code': 'P0001', 'details': None, 'hint': None})
        with pytest.raises((ValueError, PermissionError, RuntimeError)) as rejected:
            rpc('qa_action', {})
        assert str(rejected.value) != reason
