"""Exercise real Streamlit forms without external credentials or mail delivery."""
from unittest.mock import patch

import pytest

from streamlit.testing.v1 import AppTest

from core.lobbies import create_player


@pytest.fixture(autouse=True)
def allow_attempts():
    def browser(**command):
        return {"request_id": command["request_id"], "token": command.get("token", ""), "available": True}
    with patch("data.db.allow_login_attempt", return_value=True), patch("device_login._browser_storage", side_effect=browser):
        yield


def form(at, label):
    return next(button for button in at.button if button.label == label)


def fill(at, label, value):
    next(field for field in at.text_input if field.label == label).input(value)


def test_first_visit_and_direct_game_page_require_account():
    for path in ["app.py", "pages/2_Lobby.py", "pages/3_Check_in.py", "pages/4_Standings.py"]:
        at = AppTest.from_file(path).run()
        assert not at.exception
        assert at.radio(key="account_action").options == ["Create account", "Log in"]
        assert not at.tabs
        assert not at.table
        assert not any(button.label == "Create lobby" for button in at.button)


def test_registration_login_logout_and_progress_identity():
    players = []
    with patch("data.db.list_players", side_effect=lambda: players), \
         patch("data.db.insert_player", side_effect=players.append), \
         patch("data.db.get_player", side_effect=lambda pid: next((p for p in players if p.id == pid), None)):
        at = AppTest.from_file("pages/1_Profile.py").run()
        for label, value in [("First name", "Mia"), ("Surname", "Silva"), ("Username", "mia"),
                             ("Email", "MIA@example.com"), ("Password", "password8"), ("Confirm password", "password8")]:
            fill(at, label, value)
        form(at, "Create account").click().run()
        assert not at.exception
        pid = at.session_state["player_id"]
        assert players[0].id == pid
        form(at, "Log out").click().run()
        # New Streamlit process/session still signs into the stored player ID.
        at = AppTest.from_file("pages/1_Profile.py").run()
        at.radio(key="account_action").set_value("Log in").run()
        at.text_input(key="login_email").input("mia@example.com")
        at.text_input(key="login_password").input("password8")
        form(at, "Log in").click().run()
        assert not at.exception
        assert at.session_state["player_id"] == pid


def test_invalid_registration_creates_nothing():
    with patch("data.db.list_players", return_value=[]), patch("data.db.insert_player") as insert:
        at = AppTest.from_file("app.py").run()
        form(at, "Create account").click().run()
        assert at.error
        insert.assert_not_called()
        assert "player_id" not in at.session_state


def test_recovery_sends_code_and_resets_with_matching_confirmation():
    player = create_player("mia", "Mia", "Silva", "mia@example.com", "password8", "password8", [])
    with patch("data.db.list_players", return_value=[player]), \
         patch("account_ui.mail_settings", return_value={}), \
         patch("data.db.issue_password_reset", return_value=True) as issue, \
         patch("account_ui.send_reset_code") as send, \
         patch("data.db.consume_password_reset", return_value=True) as consume:
        at = AppTest.from_file("app.py").run()
        at.radio(key="account_action").set_value("Log in").run()
        at.text_input(key="recovery_email").input(player.email)
        form(at, "Send reset code").click().run()
        assert not at.exception
        issue.assert_called_once()
        send.assert_called_once()
        code = send.call_args.args[1]
        assert code != issue.call_args.args[1]
        at.radio(key="account_action").set_value("Log in").run()
        for label, value in [("Account email", player.email), ("Reset code", code),
                             ("New password", "newpass8"), ("Confirm new password", "wrong")]:
            fill(at, label, value)
        form(at, "Save new password").click().run()
        consume.assert_not_called()
        fill(at, "Confirm new password", "newpass8")
        form(at, "Save new password").click().run()
        assert not at.exception
        consume.assert_called_once()
        assert any("Password updated" in msg.value for msg in at.success)


def test_reset_password_invalid_or_expired_code_rejected():
    with patch("data.db.consume_password_reset", return_value=False):
        at = AppTest.from_file("app.py").run()
        at.radio(key="account_action").set_value("Log in").run()
        for label, value in [("Account email", "mia@example.com"), ("Reset code", "invalid"),
                             ("New password", "password8"), ("Confirm new password", "password8")]:
            fill(at, label, value)
        form(at, "Save new password").click().run()
        assert any("invalid or expired" in msg.value for msg in at.error)
        assert "player_id" not in at.session_state


def test_unknown_recovery_email_has_same_confirmation():
    with patch("data.db.list_players", return_value=[]), \
         patch("account_ui.mail_settings", return_value={}), \
         patch("account_ui.send_reset_code") as send:
        at = AppTest.from_file("app.py").run()
        at.radio(key="account_action").set_value("Log in").run()
        at.text_input(key="recovery_email").input("unknown@example.com")
        form(at, "Send reset code").click().run()
        assert any("If that email is registered" in msg.value for msg in at.success)
        send.assert_not_called()


def test_password_change_invalidates_existing_session():
    old = create_player("mia", "Mia", "Silva", "mia@example.com", "password8", "password8", [])
    changed = create_player("mia", "Mia", "Silva", "mia@example.com", "newpass8", "newpass8", [])
    with patch("data.db.get_player", return_value=changed):
        at = AppTest.from_file("pages/2_Lobby.py")
        at.session_state["player_id"] = old.id
        at.session_state["credential_version"] = old.pin_hash
        at.session_state["current_lobby_id"] = "old-lobby"
        at.run()
        assert not at.exception
        assert "player_id" not in at.session_state
        assert "current_lobby_id" not in at.session_state
        assert "Log in" in at.radio(key="account_action").options


def test_throttled_login_does_not_authenticate():
    player = create_player("mia", "Mia", "Silva", "mia@example.com", "password8", "password8", [])
    with patch("data.db.list_players", return_value=[player]), \
         patch("data.db.allow_login_attempt", return_value=False):
        at = AppTest.from_file("app.py").run()
        at.radio(key="account_action").set_value("Log in").run()
        at.text_input(key="login_email").input(player.email)
        at.text_input(key="login_password").input("password8")
        form(at, "Log in").click().run()
        assert any("Too many login attempts" in msg.value for msg in at.error)
        assert "player_id" not in at.session_state


def test_remember_checkbox_creates_device_token_and_restores_after_new_session():
    player = create_player("mia", "Mia", "Silva", "mia@example.com", "password8", "password8", [])
    token = "random-device-token"
    with patch("data.db.list_players", return_value=[player]), \
         patch("data.db.get_player", return_value=player), \
         patch("data.db.create_remembered_session", return_value=token) as create, \
         patch("data.db.revoke_remembered_session") as revoke:
        at = AppTest.from_file("pages/1_Profile.py").run()
        at.radio(key="account_action").set_value("Log in").run()
        at.text_input(key="login_email").input(player.email)
        at.text_input(key="login_password").input("password8")
        next(box for box in at.checkbox if box.label == "Remember password").check()
        form(at, "Log in").click().run()
        assert not at.exception
        create.assert_called_once_with(player)
        assert at.session_state["_device_token"] == token
        form(at, "Log out").click().run()
        revoke.assert_called_once_with(token)
        assert "player_id" not in at.session_state

    with patch("device_login._browser_storage", return_value={"request_id": "read", "token": token, "available": True}), \
         patch("data.db.get_remembered_player", return_value=player), \
         patch("data.db.get_player", return_value=player):
        fresh = AppTest.from_file("pages/1_Profile.py").run()
        assert not fresh.exception
        assert fresh.session_state["player_id"] == player.id
        assert not fresh.text_input


def test_unchecked_remember_does_not_create_persistent_access():
    player = create_player("mia", "Mia", "Silva", "mia@example.com", "password8", "password8", [])
    with patch("data.db.list_players", return_value=[player]), \
         patch("data.db.get_player", return_value=player), \
         patch("data.db.create_remembered_session") as create:
        at = AppTest.from_file("app.py").run()
        at.radio(key="account_action").set_value("Log in").run()
        at.text_input(key="login_email").input(player.email)
        at.text_input(key="login_password").input("password8")
        form(at, "Log in").click().run()
        assert not at.exception
        assert at.session_state["player_id"] == player.id
        create.assert_not_called()


def test_invalid_saved_token_is_cleared_without_access():
    def browser(**command):
        token = "invalid-token" if command["action"] == "read" else ""
        return {"request_id": command["request_id"], "token": token, "available": True}
    with patch("device_login._browser_storage", side_effect=browser), \
         patch("data.db.get_remembered_player", return_value=None):
        at = AppTest.from_file("app.py").run()
        assert not at.exception
        assert "player_id" not in at.session_state
        assert at.radio(key="account_action").options == ["Create account", "Log in"]
