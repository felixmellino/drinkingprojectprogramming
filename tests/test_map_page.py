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
    monkeypatch.setattr(db, "list_memberships_for_lobby", lambda _, **kwargs: [
        SimpleNamespace(id="me", player_id="p-me"), SimpleNamespace(id="rival", player_id="p-rival")])
    monkeypatch.setattr(db, "list_players", lambda: [
        SimpleNamespace(id="p-me", display_name="felix"), SimpleNamespace(id="p-rival", display_name="**rival**")])
    monkeypatch.setattr("phone_location._phone_location", lambda **kwargs: state["location"])
    return state


def open_map():
    return AppTest.from_file(ROOT / "pages/5_Map.py", default_timeout=10).run()


def test_map_replays_the_season_once_for_all_areas(phone, monkeypatch):
    from unittest.mock import Mock
    from core.scoring_v1 import replay_season
    replay = Mock(wraps=replay_season)
    monkeypatch.setattr('map_ui.replay_season', replay)
    page = open_map()
    assert not page.exception and len(page.get('deck_gl_json_chart')) == 1
    replay.assert_called_once()


def card(page):
    """The floating location card over the map (HTML in a markdown block)."""
    return next(m.value for m in page.markdown if 'class="game-card"' in m.value)


def hud(page):
    return next(m.value for m in page.markdown if 'class="game-hud"' in m.value)


def table(page):
    return {row["Territory"]: row for row in page.dataframe[0].value.to_dict("records")}


def test_list_shows_owner_colour_and_capture_gap(phone):
    page = open_map()
    assert not page.exception
    rows = table(page)
    assert rows["Bairro Alto"]["Status"] == "Someone else's"
    assert rows["Bairro Alto"]["What it means"] == "Owned by **rival**: you need 2 more points to take it."
    assert rows["Le Pub"]["Status"] == "Yours"
    assert rows["Le Pub"]["What it means"] == "Yours: you lead by 5 points."
    assert rows["After8"]["Status"] == "Unclaimed"
    assert len(page.get("deck_gl_json_chart")) == 1


def test_your_position_names_the_territory_you_are_in(phone):
    phone["location"] = {"lat": INSIDE[0], "lng": INSIDE[1], "accuracy_m": 12, "taken_at_ms": time.time() * 1000}
    page = open_map()
    assert not page.exception
    message = card(page)
    assert "Bairro Alto" in message and "you need 2 more points" in message
    assert any(b.label == "Check in here" for b in page.button)


def test_outside_every_territory(phone):
    phone["location"] = {"lat": OUTSIDE[0], "lng": OUTSIDE[1], "accuracy_m": 12, "taken_at_ms": time.time() * 1000}
    page = open_map()
    assert "Outside the map" in card(page)


def test_no_location_yet_still_shows_the_map(phone):
    page = open_map()
    assert "Finding you" in card(page)
    assert len(page.get("deck_gl_json_chart")) == 1


def test_inaccurate_location_is_not_used(phone):
    phone["location"] = {"lat": INSIDE[0], "lng": INSIDE[1], "accuracy_m": 90, "taken_at_ms": time.time() * 1000}
    page = open_map()
    assert "Not precise enough" in card(page) and "about 90 m" in card(page)


# -- Summary cards and quick zoom ---------------------------------------

def test_hud_counts_yours_and_free(phone):
    page = open_map()
    assert "<strong>1</strong> / 3 · 1 free" in hud(page)


def test_usernames_cannot_inject_html_into_the_card(phone, monkeypatch):
    monkeypatch.setattr(db, "list_players", lambda: [
        SimpleNamespace(id="p-me", display_name="felix"), SimpleNamespace(id="p-rival", display_name="<b>x</b>")])
    phone["location"] = {"lat": INSIDE[0], "lng": INSIDE[1], "accuracy_m": 12, "taken_at_ms": time.time() * 1000}
    message = card(open_map())
    assert "&lt;b&gt;x&lt;/b&gt;" in message and "<b>x</b>" not in message


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


def test_popup_uses_territory_totals_not_season_owner_income(phone):
    import map_ui
    rows = map_ui.territory_rows([TERRITORY, SECOND, FREE], phone["entries"], "me",
                                 {"me": "felix", "rival": "**rival**"})
    assert [(r["owner_id"], r["owner_points"], r["my_points"]) for r in rows] == [
        ("rival", 4, 3), ("me", 5, 5), (None, 0, 0)]


def test_team_popup_uses_combined_territory_points(phone):
    from dataclasses import replace
    import map_ui
    entries = [replace(e, team_id="our-team" if e.membership_id == "me" else "other-team")
               for e in phone["entries"]]
    entries.append(replace(entry("4", "teammate", "beer", "large", 3), team_id="our-team"))
    rows = map_ui.territory_rows([TERRITORY], entries, "our-team",
                                 {"our-team": "Our team", "other-team": "Other team"})
    assert rows[0]["owner_id"] == "our-team"
    assert rows[0]["owner_points"] == rows[0]["my_points"] == 6


def test_map_uses_authorized_pictures_and_survives_photo_failure(phone, monkeypatch):
    from unittest.mock import Mock
    from httpx import RequestError
    loader = Mock(side_effect=RequestError("offline"))
    monkeypatch.setattr("profile_picture_ui.load_picture", loader)
    page = AppTest.from_file(ROOT / "pages/5_Map.py", default_timeout=10)
    page.session_state["credential_version"] = "test-credential"
    page.run()
    assert not page.exception
    assert sorted(call.args for call in loader.call_args_list) == [("player", "p-me"), ("player", "p-rival")]


def test_selected_badge_opens_popup_with_escaped_name_and_both_scores(phone, monkeypatch):
    import streamlit as st
    original = st.pydeck_chart
    def selected(*args, **kwargs):
        original(*args, **kwargs)
        st.session_state["_map_open_popup"] = True
        return SimpleNamespace(selection={"indices": {"territories": [0]}})
    monkeypatch.setattr(st, "pydeck_chart", selected)
    monkeypatch.setattr(db, "list_players", lambda: [
        SimpleNamespace(id="p-me", display_name="felix"), SimpleNamespace(id="p-rival", display_name="<b>rival</b>")])
    page = open_map()
    assert not page.exception
    markup = "".join(item.value for item in page.markdown)
    assert "&lt;b&gt;rival&lt;/b&gt;" in markup
    assert '<th scope="col">Owner points</th>' in markup
    assert '<th scope="col">Your points</th>' in markup
    assert '<td>4</td><td>3</td>' in markup
