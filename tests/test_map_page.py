"""The Map page with its real widgets, a fake database and a simulated phone."""
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

import data.db as db
from core.models import Territory
from tests.test_checkins import INSIDE, OUTSIDE, TERRITORY
from tests.test_scoring_v1 import entry

ROOT = Path(__file__).resolve().parents[1]
SECOND = Territory(id="territory-b", name="Le Pub", boundary={
    "type": "Polygon",
    "coordinates": [[[-9.14, 38.70], [-9.13, 38.70], [-9.13, 38.71], [-9.14, 38.71], [-9.14, 38.70]]],
})
FREE = Territory(id="territory-c", name="After8", boundary={
    "type": "Polygon",
    "coordinates": [[[-9.13, 38.70], [-9.12, 38.70], [-9.12, 38.71], [-9.13, 38.71], [-9.13, 38.70]]],
})


@pytest.fixture
def phone(monkeypatch):
    state = {"location": None, "entries": [
        entry("1", "me", "beer", "large", 0),                                   # me: 3 in Bairro Alto
        entry("2", "rival", "shot", None, 1),                                   # rival: 4 in Bairro Alto
        entry("3", "me", "mixed", "large", 2, territory="territory-b"),         # me: 5 in Le Pub
    ]}
    monkeypatch.setattr("shared.require_login", lambda: "player")
    monkeypatch.setattr("shared.require_active_membership", lambda: ("me", "lobby", "season"))
    monkeypatch.setattr("shared.show_logged_in_as", lambda: None)
    monkeypatch.setattr("shared.get_territories", lambda: [TERRITORY, SECOND, FREE])
    monkeypatch.setattr(db, "list_drink_entries", lambda _: list(state["entries"]))
    monkeypatch.setattr(db, "list_memberships_for_lobby", lambda _: [
        SimpleNamespace(id="me", player_id="p-me"), SimpleNamespace(id="rival", player_id="p-rival")])
    monkeypatch.setattr(db, "list_players", lambda: [
        SimpleNamespace(id="p-me", display_name="felix"), SimpleNamespace(id="p-rival", display_name="**rival**")])
    monkeypatch.setattr("phone_location._phone_location", lambda **kwargs: state["location"])
    return state


def open_map():
    return AppTest.from_file(ROOT / "pages/5_Map.py", default_timeout=10).run()


def table(page):
    return {row["Territory"]: row for row in page.dataframe[0].value.to_dict("records")}


def test_list_shows_owner_colour_and_capture_gap(phone):
    page = open_map()
    assert not page.exception
    rows = table(page)
    assert rows["Bairro Alto"]["Status"] == "🔴 Someone else's"
    assert rows["Bairro Alto"]["What it means"] == "Owned by **rival**: you need 2 more points to take it."
    assert rows["Le Pub"]["Status"] == "🟢 Yours"
    assert rows["Le Pub"]["What it means"] == "Yours: you lead by 5 points."
    assert rows["After8"]["Status"] == "⚪ Unclaimed"
    assert len(page.get("deck_gl_json_chart")) == 1


def test_your_position_names_the_territory_you_are_in(phone):
    phone["location"] = {"lat": INSIDE[0], "lng": INSIDE[1], "accuracy_m": 12, "taken_at_ms": time.time() * 1000}
    page = open_map()
    assert not page.exception
    message = page.info[0].value
    assert "Bairro Alto" in message and "you need 2 more points" in message
    assert r"\*\*rival\*\*" in message  # a username can't inject Markdown


def test_outside_every_territory(phone):
    phone["location"] = {"lat": OUTSIDE[0], "lng": OUTSIDE[1], "accuracy_m": 12, "taken_at_ms": time.time() * 1000}
    page = open_map()
    assert "outside the game territories" in page.info[0].value


def test_no_location_yet_still_shows_the_map(phone):
    page = open_map()
    assert not page.info and any("Finding your location" in c.value for c in page.caption)
    assert len(page.get("deck_gl_json_chart")) == 1


def test_inaccurate_location_is_not_used(phone):
    phone["location"] = {"lat": INSIDE[0], "lng": INSIDE[1], "accuracy_m": 90, "taken_at_ms": time.time() * 1000}
    page = open_map()
    assert not page.info and any("only accurate to about 90 m" in c.value for c in page.caption)
