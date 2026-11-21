"""The Activity page through Streamlit: feed text, empty/error states, escaping and paging."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import data.db as db
from activity_ui import VERBS, drink_verb
from core.models import LobbyMembership
from tests.test_checkins import TERRITORY
from tests.test_scoring_v1 import START, entry, season
from tests.test_standings_ui import text

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def ui(monkeypatch):
    state = {
        # Mia claims the territory (3), Leo takes it (4 > 3).
        "entries": [entry("m1", "member", "beer", "large", 0), entry("l1", "other", "shot", None, 1)],
        "players": [dict(id="mia", display_name="Mia"), dict(id="leo", display_name="Leo")],
    }
    monkeypatch.setattr("shared.require_login", lambda: "mia")
    monkeypatch.setattr("shared.require_active_membership", lambda: ("member", "lobby", "season"))
    monkeypatch.setattr("shared.show_logged_in_as", lambda: None)
    monkeypatch.setattr("shared.get_territories", lambda: [TERRITORY])
    monkeypatch.setattr("core.scoring_v1.current_time", lambda: START + timedelta(minutes=10))
    monkeypatch.setattr(db, "list_drink_entries", lambda _: state["entries"])
    monkeypatch.setattr(db, "list_memberships_for_lobby", lambda _, **kwargs: [
        SimpleNamespace(id="member", player_id="mia"), SimpleNamespace(id="other", player_id="leo")])
    monkeypatch.setattr(db, "list_public_usernames", lambda: state["players"])
    monkeypatch.setattr(db, "profile_medal_launch", lambda: None)
    return state


def page():
    at = AppTest.from_file(ROOT / "pages/8_Activity.py", default_timeout=10)
    at.session_state["_validated_season"] = season()
    return at.run()


def feed(at):
    return text("\n".join(item.value for item in at.markdown if "activity-feed" in item.value))


def test_feed_shows_checkins_and_captures_newest_first(ui):
    at = page()
    assert not at.exception
    visible = feed(at)
    assert visible.index("Leo took Bairro Alto from you") < visible.index(f"Leo {drink_verb('l1')} a shot") \
        < visible.index("You claimed Bairro Alto") < visible.index(f"You {drink_verb('m1')} a large beer")
    assert "+4" in visible and "+3" in visible and "Bairro Alto, 9 min ago" in visible
    assert "·" not in visible
    assert "Game night" in visible


def test_capture_tones_follow_the_viewer(ui):
    markup = "\n".join(item.value for item in page().markdown)
    assert "activity-capture-lost" in markup and "activity-capture-yours" in markup


def test_outside_checkin_says_so_and_never_captures(ui):
    ui["entries"] = [entry("m1", "member", "shot", None, 0, territory=None)]
    visible = feed(page())
    assert "Outside territories" in visible and "claimed" not in visible


def test_empty_season_shows_an_invitation_to_check_in(ui):
    ui["entries"] = []
    at = page()
    assert not at.exception
    assert any("No activity yet" in m.value for m in at.markdown)
    assert any(b.label == "Check in" for b in at.button)


def test_database_failure_shows_an_error_not_an_empty_feed(ui, monkeypatch):
    def unavailable(*args):
        raise RuntimeError("Service unavailable")
    monkeypatch.setattr(db, "list_drink_entries", unavailable)
    at = page()
    assert not at.exception and at.error
    assert not feed(at)


def test_territory_failure_still_shows_the_feed(ui, monkeypatch):
    def unavailable():
        raise RuntimeError("Service unavailable")
    monkeypatch.setattr("shared.get_territories", unavailable)
    at = page()
    assert not at.exception and "Unknown territory" in feed(at)


def test_names_are_escaped(ui):
    ui["players"] = [dict(id="mia", display_name="Mia"), dict(id="leo", display_name="<b>Leo</b>")]
    markup = "\n".join(item.value for item in page().markdown)
    assert "<b>Leo</b>" not in markup and "&lt;b&gt;Leo&lt;/b&gt;" in markup


def test_team_mode_names_the_team(ui, monkeypatch):
    ui["entries"] = [replace(e, team_id=team) for e, team in zip(ui["entries"], ("red", "blue"))]
    monkeypatch.setattr(db, "list_lobby_teams", lambda *_: [SimpleNamespace(id="red", name="Red Lions"),
                                                            SimpleNamespace(id="blue", name="Blue Sharks")])
    at = AppTest.from_file(ROOT / "pages/8_Activity.py", default_timeout=10)
    at.session_state["_validated_season"] = season()
    at.session_state["current_team_id"] = "red"
    visible = feed(at.run())
    assert "Blue Sharks took Bairro Alto from you" in visible
    assert f"Leo (Blue Sharks) {drink_verb('l1')} a shot" in visible


def test_load_more_adds_older_events(ui):
    ui["entries"] = [entry(f"e{i}", "member", "shot", None, i * 3, territory=None) for i in range(35)]
    at = page()
    assert feed(at).count(" a shot") == 30
    next(b for b in at.button if b.label == "Load more").click().run()
    assert feed(at).count(" a shot") == 35
    assert not any(b.label == "Load more" for b in at.button)


def test_photos_switch_opens_the_gallery(ui, monkeypatch):
    switch = Mock()
    monkeypatch.setattr(st, "switch_page", switch)
    at = page()
    at.radio(key="pill_radio_activity_view_feed").set_value("Photos").run()
    assert switch.call_args.args[0] == "pages/6_Check_in_photos.py"


def test_each_checkin_keeps_its_verb_but_the_feed_varies():
    assert drink_verb("m1") == drink_verb("m1")  # same wording on every reload and restart
    assert drink_verb("m1") in VERBS
    assert len({drink_verb(f"e{i}") for i in range(50)}) > 5  # not always "drank"


def test_first_checkin_posts_three_medals_in_one_feed_row_after_reload(ui, monkeypatch):
    game = season()
    members = [LobbyMembership(member, player, "lobby", game.starts_at)
               for member, player in (("member", "mia"), ("other", "leo"))]
    monkeypatch.setattr(db, "profile_medal_launch", lambda: START + timedelta(seconds=1))
    monkeypatch.setattr(db, "list_membership_history_for_players",
                        lambda players: list(members) if set(players) == {"mia", "leo"} else [])
    monkeypatch.setattr(db, "list_seasons_for_lobbies", lambda _: [game])
    monkeypatch.setattr(db, "list_transfers_for_seasons", lambda _: [])

    for at in (page(), page()):
        assert not at.exception
        visible = feed(at)
        assert "You earned" not in visible  # Mia's check-in was before rollout.
        assert visible.count("Leo earned") == 1
        assert "Beginner in total points · Beginner in drinks · Beginner in lobbies played" in visible


def test_previous_season_win_stays_visible_in_current_lobby_feed(ui, monkeypatch):
    current = season()
    old_end = current.starts_at
    previous = replace(current, id="previous", starts_at=old_end - timedelta(days=30), ends_at=old_end)
    saved = [replace(entry("winner", "other", "shot", None, 0, territory=None),
                     season_id=previous.id, submitted_at=old_end - timedelta(days=1))]
    members = [LobbyMembership(member, player, "lobby", previous.starts_at)
               for member, player in (("member", "mia"), ("other", "leo"))]
    ui["entries"] = []
    monkeypatch.setattr(db, "profile_medal_launch", lambda: old_end - timedelta(hours=1))
    monkeypatch.setattr(db, "list_membership_history_for_players",
                        lambda players: list(members) if set(players) == {"mia", "leo"} else [])
    monkeypatch.setattr(db, "list_seasons_for_lobbies", lambda _: [current, previous])
    monkeypatch.setattr(db, "list_drink_entries", lambda season_id: saved if season_id == previous.id else [])
    monkeypatch.setattr(db, "list_drink_entries_for_seasons",
                        lambda ids: saved if list(ids) == [previous.id] else [])
    monkeypatch.setattr(db, "list_transfers_for_seasons", lambda _: [])

    at = page()
    assert not at.exception
    assert "Leo earned Beginner in total wins" in feed(at)
    assert f"Leo {drink_verb('winner')} a shot" not in feed(at)
