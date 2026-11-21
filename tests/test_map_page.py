"""The Map page with its real widgets, a fake database and a simulated phone."""
import re
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



def card(page):
    """The floating location card over the map (HTML in a markdown block)."""
    return next(m.value for m in page.markdown if 'class="game-card"' in m.value)


def hud(page):
    return next(m.value for m in page.markdown if 'class="game-hud"' in m.value)








# -- Summary cards and quick zoom ---------------------------------------

def test_hud_counts_yours_rivals_and_free(phone):
    page = open_map()
    bar = hud(page)
    assert '<b class="game-yours">1</b> yours' in bar
    assert '<b class="game-theirs">1</b> rivals' in bar
    assert '<b class="game-free">1</b> free' in bar



def test_quick_zoom_includes_jamor_golf_after_nova():
    import map_ui
    assert list(map_ui.AREAS) == ["Bairro Alto", "Lisbon", "Nova SBE", "Jamor Golf"]
    assert map_ui.AREAS["Jamor Golf"] == ["jamor-golf"]
    from data.territory_file import load_territories
    assert "jamor-golf" in {t.id for t in load_territories()}




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
    assert "Owned by Leo. You are here" in html and 'tug-pill-theirs">+4 to take it</span>' in html
    assert 'class="tug-you" style="width:36%"' in html and 'style="width:64%"' in html
    assert "You 4" in html and "Leo 7" in html
    assert '<p class="sr-only">the full sentence</p>' in html


def test_tug_of_war_on_your_territory_shows_your_lead_over_the_closest_rival():
    import map_ui
    ranking = [{"name": "felix", "points": 5, "you": True}, {"name": "Ana", "points": 3, "you": False},
               {"name": "Ben", "points": 1, "you": False}]
    html = map_ui.tug_of_war(_here("yours", 5, owner="felix", owner_points=5, ranking=ranking))
    assert 'tug-pill-yours">+2 lead</span>' in html and "Ana 3" in html and "Ben" not in html


def test_tug_of_war_alone_on_your_territory_has_a_full_bar():
    import map_ui
    ranking = [{"name": "felix", "points": 3, "you": True}]
    html = map_ui.tug_of_war(_here("yours", 3, ranking=ranking))
    assert "No rival yet 0" in html and 'class="tug-you" style="width:100%"' in html


def test_tug_of_war_escapes_names():
    import map_ui
    html = map_ui.tug_of_war(_here("theirs", 0, owner="<b>x</b>", owner_points=1, needed=2))
    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in html



def test_tapped_territory_you_are_not_in_says_owned_by_without_you_are_here():
    import map_ui
    html = map_ui.tug_of_war(_here("theirs", 1, owner_points=3, needed=3), standing_in=False)
    assert '<p class="tug-sub">Owned by Leo</p>' in html and "You are here" not in html


def test_basemap_is_light_and_dark_only_in_dark_mode(monkeypatch):
    import map_ui
    monkeypatch.setattr(map_ui, "dark_mode", lambda: False)
    assert map_ui.map_style() == "light_no_labels"
    monkeypatch.setattr(map_ui, "dark_mode", lambda: True)
    assert map_ui.map_style() == "dark_no_labels"


def test_areas_have_a_thin_outline_in_their_own_colour(phone):
    page = open_map()
    layer = next(l for l in chart_json(page)["layers"] if l["id"] == "territories")
    props = layer["data"]["features"][0]["properties"]
    assert props["line"][:3] == props["fill"][:3] and props["line"][3] > props["fill"][3]
    assert layer["lineWidthMinPixels"] == 1.5





# -- Selection flow (nothing selected by default) ----------------------------

def cards(page):
    return [m.value for m in page.markdown if 'class="game-card"' in m.value]


def tap(monkeypatch, territory_id):
    """The map reports this tap until it is redrawn with a new key (a reset
    clears the real map's selection too)."""
    import map_ui
    monkeypatch.setattr(map_ui, "render_map",
                        lambda *args, **kwargs: territory_id if kwargs["context"].endswith(":0") else None)


def test_nothing_is_selected_by_default_even_where_you_stand(phone):
    phone["location"] = {"lat": INSIDE[0], "lng": INSIDE[1], "accuracy_m": 12, "taken_at_ms": time.time() * 1000}
    page = open_map()
    assert not page.exception and not cards(page)
    assert any(b.label == "All territories 3" for b in page.button)
    assert not any(b.key and b.key.startswith("map_area_") for b in page.button)   # Lisbon / Nova pills are gone


def test_location_is_followed_invisibly_not_switched_on_the_map(phone, monkeypatch):
    calls = []
    monkeypatch.setattr("phone_location._phone_location", lambda **kwargs: calls.append(kwargs) or phone["location"])
    page = open_map()
    assert not page.exception and len(calls) == 1
    assert calls[0]["key"] == "live_location_tracker" and "mode" not in calls[0]   # the switch lives in Profile


def test_tapping_a_territory_opens_its_card_and_the_handle_closes_it(phone, monkeypatch):
    tap(monkeypatch, SECOND.id)
    page = open_map()
    assert not page.exception and page.session_state["map_selected"] == SECOND.id
    card_html = cards(page)[0]
    assert "Le Pub" in card_html and "tug-bar" in card_html and "lead</span>" in card_html
    assert "You are here" not in card_html
    next(b for b in page.button if b.key == "map_card_close").click().run()
    assert not page.exception and not cards(page) and "map_selected" not in page.session_state


def test_tapping_the_selected_territory_again_closes_the_card(phone, monkeypatch):
    tap(monkeypatch, SECOND.id)
    page = open_map()
    assert cards(page)
    page.session_state["map_last_tap"] = None        # the map reports the same area as a new tap
    page.run()
    assert not page.exception and not cards(page)


def test_unclaimed_and_standing_in_wording(phone, monkeypatch):
    tap(monkeypatch, FREE.id)
    assert "Unclaimed. Your next drink here claims it." in cards(open_map())[0]
    phone["location"] = {"lat": INSIDE[0], "lng": INSIDE[1], "accuracy_m": 12, "taken_at_ms": time.time() * 1000}
    tap(monkeypatch, TERRITORY.id)
    html = cards(open_map())[0]
    assert ". You are here" in html and "Owned by" in html and "to take it</span>" in html


def test_usernames_cannot_inject_html_into_the_card(phone, monkeypatch):
    monkeypatch.setattr(db, "list_public_usernames", lambda: [
        dict(id="p-me", display_name="felix"), dict(id="p-rival", display_name="<b>x</b>")])
    tap(monkeypatch, TERRITORY.id)
    html = cards(open_map())[0]
    assert "&lt;b&gt;x&lt;/b&gt;" in html and "<b>x</b>" not in html


def test_sheet_rows_are_sorted_easiest_to_take_first():
    import map_ui
    rows = map_ui.territory_rows([TERRITORY, SECOND, FREE], [
        entry("1", "me", "beer", "large", 0), entry("2", "rival", "shot", None, 1),
        entry("3", "me", "mixed", "large", 2, territory="territory-b")], "me", {"me": "felix", "rival": "<b>rival</b>"})
    sheet = map_ui.territory_sheet_rows(rows)
    assert [r["name"] for r in sheet] == ["Bairro Alto", "After8", "Le Pub"]
    from core.profile_photo import initials
    # Plain data: the sheet draws it with textContent, so the raw name is safe there.
    assert sheet[0]["pill"] == "+2 to take" and sheet[0]["avatar"] == initials("<b>rival</b>")
    assert sheet[0]["sub"].startswith("Owned by <b>rival</b>, you")
    assert sheet[1]["pill"] == "Claim it" and sheet[2]["pill"] == "+5 lead"
    assert "you need 2 more points" in sheet[0]["detail"]          # screen-reader sentence travels along


def test_picking_a_name_in_the_sheet_selects_it_and_zooms_there(phone, monkeypatch):
    import map_ui
    seen = {}
    real = map_ui.render_map
    def spy(rows, location, accuracy_m, focus, **kwargs):
        seen["focus"], seen["selected"] = focus, kwargs.get("selected")
        return None
    monkeypatch.setattr(map_ui, "render_map", spy)
    page = open_map()
    assert seen["focus"] == "Lisbon" and seen["selected"] is None
    monkeypatch.setattr(map_ui, "_territory_sheet", lambda **kwargs: {"action": "select", "id": SECOND.id})
    next(b for b in page.button if b.label.startswith("All territories")).click().run()
    assert not page.exception
    assert page.session_state["map_selected"] == SECOND.id and seen == {"focus": SECOND.id, "selected": SECOND.id}
    assert "Le Pub" in cards(page)[0] and "map_sheet_open" not in page.session_state


def test_swiping_the_sheet_down_just_closes_it(phone, monkeypatch):
    import map_ui
    monkeypatch.setattr(map_ui, "_territory_sheet", lambda **kwargs: {"action": "close"})
    page = open_map()
    next(b for b in page.button if b.label.startswith("All territories")).click().run()
    assert not page.exception and "map_sheet_open" not in page.session_state and not cards(page)


def test_unknown_ids_from_the_sheet_are_ignored(phone, monkeypatch):
    import map_ui
    monkeypatch.setattr(map_ui, "_territory_sheet", lambda **kwargs: {"action": "select", "id": "not-a-territory"})
    page = open_map()
    next(b for b in page.button if b.label.startswith("All territories")).click().run()
    assert not page.exception and "map_selected" not in page.session_state


def test_view_zooms_to_a_single_territory():
    import map_ui
    rows = map_ui.territory_rows([TERRITORY, SECOND, FREE], [], "me", {})
    one = map_ui.view_for(rows, SECOND.id, None)
    lngs = [p[0] for p in SECOND.boundary["coordinates"][0]]
    assert abs(one.longitude - (min(lngs) + max(lngs)) / 2) < 1e-9 and one.zoom <= 16.5


def test_selected_area_gets_a_thicker_outline_on_top(phone):
    page = open_map()
    assert not any(l["id"] == "selected-outline" for l in chart_json(page)["layers"])   # nothing selected
    page.session_state["map_selected"] = SECOND.id
    page.run()
    outline = next(l for l in chart_json(page)["layers"] if l["id"] == "selected-outline")
    assert outline["lineWidthMinPixels"] == 3.5 and outline["filled"] is False
    assert [f["properties"]["id"] for f in outline["data"]["features"]] == [SECOND.id]
