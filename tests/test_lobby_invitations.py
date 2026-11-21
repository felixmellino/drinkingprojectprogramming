from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from postgrest.exceptions import APIError
from streamlit.testing.v1 import AppTest

import data.db as db
import password_email
from core.lobbies import create_player
from tests.test_lobby_ui import click, page, ui  # noqa: F401 (shared lobby fixture)

ROOT = Path(__file__).resolve().parents[1]
INVITE = "865ddf18-db73-4dda-8b18-b6fe5e117cbe"
ROW = dict(invite_id=INVITE, lobby_name="Friday Night", inviter_name="Alex")


@pytest.mark.parametrize("mail_fails", [False, True])
def test_creator_selects_accepted_friend_and_emails_only_after_saving(ui, monkeypatch, mail_fails):
    ui["users"].extend([dict(id="maya", display_name="Maya"), dict(id="pending", display_name="PendingFriend")])
    ui["relationships"].extend([
        dict(sender_id="maya", recipient_id="me", status="accepted"),
        dict(sender_id="me", recipient_id="pending", status="pending"),
        dict(sender_id="me", recipient_id="leo-id", status="accepted"),
    ])
    ui["lobby_members"]["new"][-1].left_at = None
    monkeypatch.setattr(db, "get_player", lambda _: SimpleNamespace(email="alex@example.com", pin_hash="current"))
    issue = Mock(return_value={**ROW, "recipient_email": "maya@example.com"})
    deliver = Mock(side_effect=RuntimeError("provider details") if mail_fails else None)
    sequence = Mock()
    sequence.attach_mock(issue, "issue")
    sequence.attach_mock(deliver, "deliver")
    monkeypatch.setattr(db, "issue_lobby_invitation", issue)
    monkeypatch.setattr("lobby_invite_ui.send_lobby_invite_email", deliver)
    at = page()
    at.session_state["player_id"] = "me"
    at.session_state["credential_version"] = "current"
    at.button(key="open_lobby_new").click().run()
    click(at, "Invite player")
    assert "Invite PendingFriend" not in [b.label for b in at.button]
    assert "Invite Leo" not in [b.label for b in at.button]
    click(at, "Invite Maya")
    assert not at.exception
    assert [call[0] for call in sequence.mock_calls] == ["issue", "deliver"]
    issue.assert_called_once_with("me", "new", "maya")
    deliver.assert_called_once_with("maya@example.com", INVITE, "Alex", "Friday Night")
    if mail_fails:
        assert "Pending invites" in at.warning[-1].value
        assert "provider details" not in at.warning[-1].value
    else:
        assert "submitted for email delivery" in at.success[-1].value


@pytest.mark.parametrize(("response", "from_email"), [("accept", True), ("decline", False)])
def test_recipient_can_respond_from_email_or_pending_invites(ui, monkeypatch, response, from_email):
    invitations = [ROW]
    monkeypatch.setattr(db, "pending_lobby_invitations", lambda _: list(invitations))
    monkeypatch.setattr(db, "get_player", lambda _: SimpleNamespace(email="maya@example.com", pin_hash="current"))

    def respond(*_):
        invitations.clear()
        return "Friday Night"

    action = Mock(side_effect=respond)
    monkeypatch.setattr(db, "respond_to_lobby_invitation", action)
    at = page()
    at.session_state["player_id"] = "me"
    at.session_state["credential_version"] = "current"
    if from_email:
        at.query_params["lobby_invite"] = INVITE
        at.run()
    action.assert_not_called()
    assert any(header.value == "Pending invites" for header in at.subheader)
    click(at, response.title())
    assert not at.exception
    action.assert_called_once_with("me", INVITE, response)
    assert "lobby_invite" not in at.query_params
    assert not any(header.value == "Pending invites" for header in at.subheader)
    assert any("Friday Night" in message.value for message in at.success)


def test_full_lobby_keeps_invite_on_screen(ui, monkeypatch):
    monkeypatch.setattr(db, "pending_lobby_invitations", lambda _: [ROW])
    monkeypatch.setattr(db, "get_player", lambda _: SimpleNamespace(email="maya@example.com", pin_hash="current"))
    monkeypatch.setattr(db, "respond_to_lobby_invitation", Mock(side_effect=APIError({"message": "lobby_full"})))
    at = page()
    at.session_state["player_id"] = "me"
    at.session_state["credential_version"] = "current"
    click(at, "Accept")
    assert "This lobby is full." in at.error[-1].value
    assert "Decline" in [b.label for b in at.button]


def test_direct_link_prompts_login_and_retains_invitation(monkeypatch):
    player = create_player("maya", "Maya", "Silva", "maya@example.com", "password8", "password8", [])
    monkeypatch.setattr("shared.sync_storage", lambda: "")
    monkeypatch.setattr("shared.bottom_navigation", lambda: None)
    monkeypatch.setattr("shared.restore_selection", lambda _: None)
    monkeypatch.setattr(db, "authenticate_login", lambda *_: player)
    monkeypatch.setattr(db, "get_player", lambda _: player)
    monkeypatch.setattr(db, "list_memberships_for_player", lambda _: [])
    pending = Mock(return_value=[ROW])
    monkeypatch.setattr(db, "pending_lobby_invitations", pending)
    at = AppTest.from_file(ROOT / "pages/2_Lobby.py")
    at.query_params["lobby_invite"] = INVITE
    at.run()
    assert at.radio(key="account_action").value == "Log in"
    pending.assert_not_called()
    at.text_input(key="login_email").input(player.email)
    at.text_input(key="login_password").input("password8")
    click(at, "Log in")
    assert not at.exception
    pending.assert_called_with(player.id)
    assert at.query_params["lobby_invite"] == INVITE
    assert "Accept" in [b.label for b in at.button]


def test_email_payload_uses_review_link_and_escapes_names(monkeypatch):
    send = Mock()
    settings = {"BREVO_API_KEY": "test"}
    monkeypatch.setattr(password_email, "email_settings", lambda **_: settings)
    monkeypatch.setattr(password_email, "_send_email", send)
    password_email.send_lobby_invite_email("maya@example.com", INVITE, "<Alex>", "A&B")
    email, payload, sent_settings = send.call_args.args
    assert email == "maya@example.com" and sent_settings == settings
    link = urlsplit(next(line.split()[-1] for line in payload["textContent"].splitlines() if line.startswith("Review")))
    assert link.scheme == "https" and link.path == "/Lobby"
    assert parse_qs(link.query) == {"lobby_invite": [INVITE]}
    assert "&lt;Alex&gt;" in payload["htmlContent"] and "A&amp;B" in payload["htmlContent"]
