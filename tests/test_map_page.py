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
    monkeypatch.setattr(db, "list_public_usernames", lambda: [
        dict(id="p-me", display_name="felix"), dict(id="p-rival", display_name="**rival**")])
    monkeypatch.setattr("phone_location._phone_location", lambda **kwargs: state["location"])
    return state


def open_map():
    return AppTest.from_file(ROOT / "pages/5_Map.py", default_timeout=10).run()


@pytest.mark.parametrize('problem, words', [('denied', ['blocked', 'browser settings']),
                                         ('unsupported', ['cannot share', 'HTTPS']),
                                         ('timeout', ['too long', 'off and on'])])
def test_location_help_explains_the_actual_failure_on_tap(phone, problem, words):
    from tests.feedback_helpers import assert_blocked
    phone['location'] = {'error': problem}
    page = open_map()
    assert not page.error
    assert_blocked(page, 'Location help', *words)


def test_map_replays_the_season_once_for_all_areas(phone, monkeypatch):
    from unittest.mock import Mock
    from core.scoring_v1 import replay_season
    replay = Mock(wraps=replay_season)
    monkeypatch.setattr('map_ui.replay_season', replay)
    page = open_map()
    assert not page.exception and len(page.get('deck_gl_json_chart')) == 1
    replay.assert_called_once()


def test_map_has_one_compact_location_switch_that_also_follows_the_position(phone, monkeypatch):
    calls = []
    monkeypatch.setattr("phone_location._phone_location", lambda **kwargs: calls.append(kwargs) or phone["location"])
    page = open_map()
    assert not page.exception
    assert len(calls) == 1, "one component only: the switch itself follows, no second invisible tracker"
    assert calls[0]["mode"] == "switch" and calls[0]["compact"] is True and calls[0]["follow"] is True
    assert calls[0]["key"] == "location_switch_map"   # a different key than the Profile switch


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
    assert not any(b.label == "Check in here" for b in page.button)  # checking in is the + tab


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

def test_hud_counts_yours_rivals_and_free(phone):
    page = open_map()
    bar = hud(page)
    assert '<b class="game-yours">1</b> yours' in bar
    assert '<b class="game-theirs">1</b> rivals' in bar
    assert '<b class="game-free">1</b> free' in bar


def test_usernames_cannot_inject_html_into_the_card(phone, monkeypatch):
    monkeypatch.setattr(db, "list_public_usernames", lambda: [
        dict(id="p-me", display_name="felix"), dict(id="p-rival", display_name="<b>x</b>")])
    phone["location"] = {"lat": INSIDE[0], "lng": INSIDE[1], "accuracy_m": 12, "taken_at_ms": time.time() * 1000}
    message = card(open_map())
    assert "&lt;b&gt;x&lt;/b&gt;" in message and "<b>x</b>" not in message


def test_quick_zoom_includes_jamor_golf_after_nova():
    import map_ui
    assert list(map_ui.AREAS) == ["Bairro Alto", "Lisbon", "Nova SBE", "Jamor Golf"]
    assert map_ui.AREAS["Jamor Golf"] == ["jamor-golf"]
    from data.territory_file import load_territories
    assert "jamor-golf" in {t.id for t in load_territories()}


def test_two_icon_buttons_lisbon_and_nova_and_the_map_starts_on_me_only_with_a_location(phone, monkeypatch):
    import map_ui
    seen = []
    real = map_ui.render_map
    monkeypatch.setattr(map_ui, "render_map", lambda rows, location, accuracy, focus, **kw: seen.append(focus) or real(rows, location, accuracy, focus, **kw))
    page = open_map()
    labels = [b.label for b in page.button if b.key and b.key.startswith("map_area_")]
    assert labels == ["Lisbon", "Nova"], "only two buttons, no Me / Bairro Alto / Jamor / All"
    assert not page.get("button_group"), "no stretched chip row any more"
    assert seen[-1] == "Lisbon", "no usable location: start on Lisbon"
    phone["location"] = {"lat": INSIDE[0], "lng": INSIDE[1], "accuracy_m": 12, "taken_at_ms": time.time() * 1000}
    page = open_map()
    assert seen[-1] == map_ui.ME, "usable location, nothing picked: start on me"
    next(b for b in page.button if b.key == "map_area_nova").click().run()
    assert not page.exception and seen[-1] == "Nova SBE"
    assert ".st-key-map_area_nova button{color:var(--accent-ink)" in " ".join(m.value for m in page.markdown)
    next(b for b in page.button if b.key == "map_area_nova").click().run()   # tap the picked one again: back to me
    assert seen[-1] == map_ui.ME


def test_a_wrong_remembered_area_does_not_break_the_page(phone):
    page = AppTest.from_file(ROOT / "pages/5_Map.py", default_timeout=10)
    page.session_state["map_area"] = "Bairro Alto"
    page.run()
    assert not page.exception


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


@pytest.mark.parametrize('failure',[RuntimeError('offline'),ValueError('sign-in changed')])
def test_map_uses_authorized_pictures_and_survives_photo_failure(phone, monkeypatch, failure):
    from unittest.mock import Mock
    from httpx import RequestError
    loader = Mock(side_effect=failure)
    monkeypatch.setattr("profile_picture_ui.load_pictures", loader)
    page = AppTest.from_file(ROOT / "pages/5_Map.py", default_timeout=10)
    page.session_state["credential_version"] = "test-credential"
    page.run()
    assert not page.exception
    loader.assert_called_once_with('player', ['p-me','p-rival'])


def chart_json(page):
    import json
    return json.loads(page.get("deck_gl_json_chart")[0].proto.json)


def test_map_sends_only_territory_ids_and_selects_on_tap(phone, monkeypatch):
    monkeypatch.setattr(db, "list_public_usernames", lambda: [
        dict(id="p-me", display_name="felix"), dict(id="p-rival", display_name="<b>rival</b>")])
    page = open_map()
    assert not page.exception
    chart = page.get("deck_gl_json_chart")[0].proto
    assert chart.selection_mode and not chart.tooltip                # a tap selects; no white tooltip
    layers = {layer["id"]: layer for layer in chart_json(page)["layers"]}
    assert layers["owner-badges"]["pickable"] is False             # taps reach the territory under a badge
    props = layers["territories"]["data"]["features"][0]["properties"]
    assert props["id"] == TERRITORY.id
    assert "<b>rival</b>" not in chart.json and "rival" not in str(props)  # names stay server-side


def test_selected_territory_reads_only_known_ids():
    import map_ui
    event = SimpleNamespace(selection={"objects": {"territories": [{"properties": {"id": "territory-b"}}]}})
    assert map_ui.selected_territory(event, {"territory-a", "territory-b"}) == "territory-b"
    assert map_ui.selected_territory(event, {"territory-a"}) is None                     # unknown id ignored
    assert map_ui.selected_territory(SimpleNamespace(selection={}), {"territory-a"}) is None
    assert map_ui.selected_territory(None, {"territory-a"}) is None


def test_tapping_a_territory_shows_its_tug_of_war_without_standing_in_it(phone, monkeypatch):
    import map_ui
    monkeypatch.setattr(map_ui, "render_map", lambda *args, **kwargs: SECOND.id)  # tapped Le Pub
    message = card(open_map())                                       # no location yet
    assert "Le Pub" in message and "tug-bar" in message and "your lead" in message
    assert "You are in" not in message and "Finding you" not in message


def test_tapping_an_unclaimed_territory_says_the_next_drink_claims_it(phone, monkeypatch):
    import map_ui
    monkeypatch.setattr(map_ui, "render_map", lambda *args, **kwargs: FREE.id)
    message = card(open_map())
    assert "After8" in message and "Your next drink here claims it." in message and "tug-bar" not in message


def test_tapping_the_territory_you_stand_in_keeps_you_are_in(phone, monkeypatch):
    import map_ui
    monkeypatch.setattr(map_ui, "render_map", lambda *args, **kwargs: TERRITORY.id)
    phone["location"] = {"lat": INSIDE[0], "lng": INSIDE[1], "accuracy_m": 12, "taken_at_ms": time.time() * 1000}
    message = card(open_map())
    assert "You are in · owned by" in message and "pts to take it" in message


def test_territory_rows_carry_a_ranking_in_standings_order(phone):
    import map_ui
    rows = map_ui.territory_rows([TERRITORY, FREE], phone["entries"], "me", {"me": "felix", "rival": "rival"})
    assert [(r["id"], r["name"], r["points"], r["you"]) for r in rows[0]["ranking"]] == [
        ("rival", "rival", 4, False), ("me", "felix", 3, True)]
    assert rows[1]["ranking"] == []


# -- Tug-of-war card (owned territory you stand in) ---------------------

def _here(status, mine, *, owner="Leo", owner_points=0, needed=None, ranking=None):
    return {"name": "Bairro Alto", "status": status, "my_points": mine, "owner": owner,
            "owner_points": owner_points, "needed": needed, "ranking": ranking or [],
            "detail": "the full sentence"}


def test_tug_of_war_on_a_rivals_territory_shows_points_to_take_it():
    import map_ui
    html = map_ui.tug_of_war(_here("theirs", 4, owner_points=7, needed=4))
    assert "owned by Leo" in html and "<b>4</b><em>pts to take it</em>" in html
    assert 'class="tug-you" style="width:36%"' in html and 'style="width:64%"' in html
    assert "You 4" in html and "Leo 7" in html
    assert '<p class="sr-only">the full sentence</p>' in html


def test_tug_of_war_on_your_territory_shows_your_lead_over_the_closest_rival():
    import map_ui
    ranking = [{"name": "felix", "points": 5, "you": True}, {"name": "Ana", "points": 3, "you": False},
               {"name": "Ben", "points": 1, "you": False}]
    html = map_ui.tug_of_war(_here("yours", 5, owner="felix", owner_points=5, ranking=ranking))
    assert "<b>+2</b><em>your lead</em>" in html and "Ana 3" in html and "Ben" not in html


def test_tug_of_war_alone_on_your_territory_has_a_full_bar():
    import map_ui
    ranking = [{"name": "felix", "points": 3, "you": True}]
    html = map_ui.tug_of_war(_here("yours", 3, ranking=ranking))
    assert "No rival yet 0" in html and 'class="tug-you" style="width:100%"' in html


def test_tug_of_war_escapes_names():
    import map_ui
    html = map_ui.tug_of_war(_here("theirs", 0, owner="<b>x</b>", owner_points=1, needed=2))
    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in html


def test_card_uses_tug_of_war_inside_a_rivals_territory(phone):
    phone["location"] = {"lat": INSIDE[0], "lng": INSIDE[1], "accuracy_m": 12, "taken_at_ms": time.time() * 1000}
    message = card(open_map())
    assert 'class="tug-bar"' in message and "pts to take it" in message
