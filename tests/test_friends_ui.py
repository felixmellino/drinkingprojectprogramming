"""Run the real Profile page with a persistent fake repository, no secrets."""
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from core.friends import transition
from core.models import Player

ROOT = Path(__file__).resolve().parents[1]


def button(at, label):
    return next(b for b in at.button if b.label == label)


def test_profile_friend_workflow_and_new_sessions():
    players = [Player(p, p.title(), "PrivateFirst", "PrivateLast", "hash", f"{p}@private.test") for p in ("alice", "bob", "carol")]
    rows = {}

    def save(actor, other, action):
        key = tuple(sorted((actor, other)))
        row = transition(actor, other, action, rows.get(key), datetime.now(timezone.utc))
        rows[key] = {**row, "updated_at": datetime.now(timezone.utc).isoformat()}

    def page(pid):
        at = AppTest.from_file(str(ROOT / "pages/1_Profile.py"))
        at.session_state["player_id"] = pid
        at.session_state["credential_version"] = "hash"
        at.run()
        assert not at.exception
        return at

    with ExitStack() as stack:
        stack.enter_context(patch("device_login.sync_storage", return_value=None))
        stack.enter_context(patch("data.db.get_player", side_effect=lambda pid: next(p for p in players if p.id == pid)))
        stack.enter_context(patch("data.db.list_public_usernames", return_value=[{"id": p.id, "display_name": p.display_name} for p in players]))
        stack.enter_context(patch("data.db.list_friendships", side_effect=lambda pid: [r.copy() for r in rows.values() if pid in (r["sender_id"], r["recipient_id"])]))
        stack.enter_context(patch("data.db.change_friendship", side_effect=save))
        alice = page("alice")
        alice.text_input[0].input("BO").run()
        button(alice, "Send friend request").click().run()
        assert not alice.exception
        assert any(b.label == "Cancel request" for b in alice.button)
        bob = page("bob")
        button(bob, "Accept").click().run()
        assert not bob.exception
        assert any(b.label == "Remove friend" for b in bob.button)
        fresh_alice = page("alice")
        assert any(b.label == "Remove friend" for b in fresh_alice.button)
        carol = page("carol")
        assert not any(b.label in ("Accept", "Remove friend", "Cancel request") for b in carol.button)
        assert not any("alice@" in str(e.value) for e in carol.text)
        button(fresh_alice, "Remove friend").click().run()
        assert not any(b.label == "Remove friend" for b in page("bob").button)
        alice = page("alice")
        alice.text_input[0].input("bob").run()
        button(alice, "Send friend request").click().run()
        button(alice, "Cancel request").click().run()
        assert not any(b.label == "Accept" for b in page("bob").button)
        alice.text_input[0].input("bob").run()
        button(alice, "Send friend request").click().run()
        bob = page("bob")
        button(bob, "Decline").click().run()
        alice = page("alice")
        alice.text_input[0].input("bob").run()
        button(alice, "Send friend request").click().run()
        assert any("10 minutes" in e.value for e in alice.error)
        assert not alice.exception


def test_friend_service_failure_preserves_profile():
    player = Player("alice", "Alice", "Private", "Name", "hash", "private@test.com")
    with patch("device_login.sync_storage", return_value=None), patch("data.db.get_player", return_value=player), patch("data.db.list_public_usernames", side_effect=RuntimeError("missing migration")):
        at = AppTest.from_file(str(ROOT / "pages/1_Profile.py"))
        at.session_state["player_id"] = player.id
        at.session_state["credential_version"] = player.pin_hash
        at.run()
        assert not at.exception
        assert at.error
        assert any(b.label == "Log out" for b in at.button)
