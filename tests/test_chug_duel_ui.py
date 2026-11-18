"""Two independent Streamlit sessions exercise the actual duel widgets."""
from copy import deepcopy
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

import data.db as db
import minigames_ui as ui
from core.models import Lobby, LobbyMembership
from tests.test_scoring_v1 import START, season

ROOT = Path(__file__).resolve().parents[1]


def button(page, label):
    return next(b for b in page.button if b.label == label)


@pytest.fixture
def service(monkeypatch):
    game = season()
    lobby = Lobby("lobby", "Duel lobby", "CODE")
    members = [LobbyMembership("a", "pa", "lobby", START), LobbyMembership("b", "pb", "lobby", START)]
    state = {"duels": [], "board": None, "photo": None, "location": ((38.7, -9.1), 10, None), "starts": 0}
    monkeypatch.setattr(db, "list_seasons_for_lobby", lambda _: [game])
    monkeypatch.setattr(db, "list_lobbies", lambda: [lobby])
    monkeypatch.setattr(db, "list_memberships_for_lobby", lambda _: members)
    monkeypatch.setattr(db, "list_public_usernames", lambda: [{"id": "pa", "display_name": "Alice"}, {"id": "pb", "display_name": "Bob"}])
    monkeypatch.setattr(db, "list_chug_duels", lambda *args: deepcopy(state["duels"]))
    monkeypatch.setattr("shared.require_login", lambda: __import__("streamlit").session_state["player_id"])
    monkeypatch.setattr("shared.require_active_membership", lambda: (__import__("streamlit").session_state["member"], "lobby", "season"))
    monkeypatch.setattr(ui, "current_time", lambda: START)
    monkeypatch.setattr(ui, "track_location", lambda: None)
    monkeypatch.setattr(ui, "current_location", lambda: state["location"])
    monkeypatch.setattr(ui, "camera_photo", lambda **kwargs: state["photo"])
    monkeypatch.setattr(ui, "duel_board", lambda *args: state["board"])

    def invite(actor, sid, iid, opponent, drink, size):
        assert actor == "pa" and opponent == "b"
        duel = dict(id=iid, season_id=sid, challenger_id="a", opponent_id="b", game_night="2026-11-19",
                    status="invited", drink_type=drink, size=size, play_at=None, created_at=START.isoformat(),
                    accepted_at=None, challenger_entry_id=str(uuid4()), opponent_entry_id=str(uuid4()))
        state["duels"].append(duel)
        return deepcopy(duel)

    def action(actor, did, selected, winner=None):
        d = next(d for d in state["duels"] if d["id"] == did)
        if selected == "accept":
            assert actor == "pb"
            d.update(status="accepted", accepted_at=START.isoformat())
        elif selected == "arm":
            assert actor == "pa"
            d["play_at"] = START.isoformat()
        elif selected == "finish":
            assert actor == "pa" and winner in {"a", "b"}
            d.update(status="completed", winner_id=winner)
        elif selected in {"cancel", "decline", "abort"}:
            d["status"] = "aborted" if d["status"] == "started" else {"cancel": "cancelled", "decline": "declined", "abort": "cancelled"}[selected]
        return deepcopy(d)

    def start(actor, lid, sid, did, photo, at, gps, accuracy):
        assert actor == "pa" and gps == state["location"][0] and photo
        state["starts"] += 1
        d = next(d for d in state["duels"] if d["id"] == did)
        d["status"] = "started"
        return deepcopy(d)

    monkeypatch.setattr(db, "invite_chug_duel", invite)
    monkeypatch.setattr(db, "chug_duel_action", action)
    monkeypatch.setattr(db, "start_chug_duel", start)
    state.update(lobby=lobby, members=members)
    return state


def open_page(player="pa", member="a"):
    page = AppTest.from_file(ROOT / "pages/7_Minigames.py", default_timeout=10)
    page.session_state["player_id"] = player
    page.session_state["member"] = member
    return page.run()


def test_invite_accept_on_other_session_shared_capture_and_result(service):
    host, guest = open_page(), open_page("pb", "b")
    assert not host.exception and not guest.exception
    button(host, "Send challenge").click().run()
    guest.run()
    assert not guest.exception and button(guest, "Accept duel")
    button(guest, "Accept duel").click().run()
    host.run()
    assert not any(b.label == "Save shared check-in & open duel" for b in host.button)
    photo = BytesIO()
    Image.new("RGB", (4, 4)).save(photo, "JPEG")
    service["photo"] = photo
    host.run()
    assert not host.exception and button(host, "Save shared check-in & open duel")
    service["location"] = (None, None, "denied")
    host.run()
    assert button(host, "Save shared check-in & open duel").disabled
    assert service["starts"] == 0
    service["location"] = ((38.7, -9.1), 10, None)
    host.run()
    button(host, "Save shared check-in & open duel").click().run()
    assert not host.exception and service["starts"] == 1
    guest.run()
    assert any("challenger's phone" in item.value for item in guest.info)
    did = service["duels"][0]["id"]
    service["board"] = {"duel_id": did, "phase": "ready"}
    host.run()
    assert service["duels"][0]["play_at"]
    service["board"] = {"duel_id": did, "phase": "result", "winner": "opponent"}
    host.run()
    guest.run()
    assert not host.exception and not guest.exception
    assert any("Bob won" in item.value for item in guest.success)
    # A fresh session recovers the saved outcome instead of opening a new game.
    reopened = open_page("pb", "b")
    assert any("Bob won" in item.value for item in reopened.success)


def test_decline_releases_allowance_and_host_can_invite_again(service):
    host = open_page()
    button(host, "Send challenge").click().run()
    guest = open_page("pb", "b")
    button(guest, "Decline").click().run()
    host.run()
    assert button(host, "Send challenge")
    button(host, "Send challenge").click().run()
    assert len(service["duels"]) == 2
    assert service["duels"][0]["status"] == "declined"


def test_outage_and_membership_denial_show_actionable_errors(service, monkeypatch):
    monkeypatch.setattr(db, "list_chug_duels", Mock(side_effect=RuntimeError("Chug Duel setup is not complete. Please contact the app organizer.")))
    page = open_page()
    assert not page.exception and any("setup" in item.value for item in page.error)
    assert not any(b.label == "Send challenge" for b in page.button)
    monkeypatch.setattr(db, "list_memberships_for_lobby", lambda _: [])
    page.run()
    assert not page.exception and any("membership" in item.value for item in page.error)


def test_team_opponent_choices_exclude_own_team(service):
    service["lobby"].game_mode = "team"
    for member in service["members"]:
        member.team_id = "red"
    page = open_page()
    assert not page.exception and not any(b.label == "Send challenge" for b in page.button)
    assert any("rival team" in item.value for item in page.info)
