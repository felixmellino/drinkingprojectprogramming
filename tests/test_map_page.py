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


# -- Summary cards and quick zoom ---------------------------------------

def test_summary_counts_yours_free_and_easiest_capture(phone):
    page = open_map()
    metrics = {m.label: m.value for m in page.metric}
    assert metrics["Yours"] == "1 of 3"
    assert metrics["Unclaimed"] == "1"
    assert metrics["Easiest to take"] == "Bairro Alto"


def test_quick_zoom_offers_the_areas_and_me_only_with_a_location(phone):
    page = open_map()
    assert page.get("button_group")[0].proto.options and not any(
        "Me" in o.content for o in page.get("button_group")[0].proto.options)
    phone["location"] = {"lat": INSIDE[0], "lng": INSIDE[1], "accuracy_m": 12, "taken_at_ms": time.time() * 1000}
    page = open_map()
    assert "Me" in page.get("button_group")[0].proto.options[0].content


def test_summary_helper_picks_the_cheapest_territory_to_take():
    import map_ui
    rows = [
        {"name": "A", "status": "theirs", "needed": 5},
        {"name": "B", "status": "theirs", "needed": 2},
        {"name": "C", "status": "yours", "needed": None},
        {"name": "D", "status": "free", "needed": None},
    ]
    assert map_ui.summary(rows) == {"yours": 1, "total": 4, "free": 1, "easiest": ("B", 2)}
    assert map_ui.summary([])["easiest"] is None


def test_zoom_fits_an_area_and_centres_on_it():
    import map_ui
    rows = [{"id": "nova-sbe", "boundary": {"coordinates": [[[-9.328, 38.673], [-9.323, 38.673],
                                                              [-9.323, 38.679], [-9.328, 38.673]]]}}]
    view = map_ui.view_for(rows, "Nova SBE", None)
    assert abs(view.latitude - 38.676) < 0.001 and abs(view.longitude - -9.3255) < 0.001
    assert 14 <= view.zoom <= 17
    me = map_ui.view_for(rows, map_ui.ME, (38.7, -9.1))
    assert (me.latitude, me.longitude) == (38.7, -9.1)
