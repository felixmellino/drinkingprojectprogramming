"""Use the actual Streamlit widgets with frozen clocks and isolated services."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import time
from unittest.mock import Mock

import pytest
from httpx import ReadTimeout
from PIL import Image
import streamlit as st
from streamlit.testing.v1 import AppTest

import data.db as db
import core.scoring_v1 as rules
from tests.test_checkins import INSIDE, TERRITORY
from tests.test_scoring_v1 import START, entry, season
from tests.feedback_helpers import assert_blocked

ROOT = Path(__file__).resolve().parents[1]


def button(page, label):
    return next(item for item in page.button if item.label == label)


def radio(page, label):
    return next(item for item in page.radio if item.label == label)


@pytest.fixture
def ui(monkeypatch):
    monkeypatch.setattr(db, 'list_season_transfers', lambda _: [])
    game = season()
    state = {"now": START, "entries": [], "lose_reply": False, "calls": 0, "photo": None, "location": None}
    camera = BytesIO()
    Image.new("RGB", (12, 6)).save(camera, "JPEG")
    camera.file_id = "fresh-camera-capture"
    state["photo"] = camera
    monkeypatch.setattr("shared.require_login", lambda: "player")
    monkeypatch.setattr("shared.require_active_membership", lambda: ("member", "lobby", "season"))
    monkeypatch.setattr("shared.show_logged_in_as", lambda: None)
    monkeypatch.setattr("shared.get_territories", lambda: [TERRITORY])
    monkeypatch.setattr(rules, "current_time", lambda: state["now"])
    monkeypatch.setattr(db, "list_seasons_for_lobby", lambda _: [game])
    monkeypatch.setattr(db, 'focus_status', lambda *args: {'boost_ends_at': None})
    monkeypatch.setattr(db, 'time_status', lambda *args: {'boost_ends_at': None})
    # UI service double; authorization/batching itself is tested against the
    # stateful database double in test_photo_lifecycle/test_photo_privacy.
    def batch(p, l, ids):
        # Like the real function: one authorization batch holds at most MAX_PHOTO_BATCH photos.
        if len(list(dict.fromkeys(ids))) > db.MAX_PHOTO_BATCH:
            raise ValueError('Load at most twelve check-in photos at once.')
        return {eid: db.download_checkin_photo(p, l, eid) for eid in ids}
    monkeypatch.setattr(db, 'download_checkin_photos', batch)
    monkeypatch.setattr(db, "list_drink_entries_for_membership", lambda _: list(state["entries"]))
    monkeypatch.setattr(db, "list_drink_entries", lambda _: list(state["entries"]))
    monkeypatch.setattr('camera_capture.camera_photo', lambda key: state["photo"] if key.endswith("_0") else None)
    # The automatic location tracker is a browser component AppTest can't run;
    # this returns what the phone would send (None = no reading yet).
    monkeypatch.setattr("phone_location._phone_location", lambda **kwargs: state["location"])

    def save(player, lobby, model, photo):
        state["calls"] += 1
        assert player == "player" and lobby == "lobby"
        with Image.open(BytesIO(photo)) as saved:
            assert not saved.getexif()
        model = replace(model, event_order=max((item.event_order or 0 for item in state["entries"]), default=0) + 1, owner_bonus_quarters=model.points_awarded,
                        owner_membership_id="other-member")
        state["entries"].append(model)
        if state["lose_reply"]:
            raise ReadTimeout("Response lost after committed write")
        return model
    monkeypatch.setattr(db, "save_drink_entry_photo", save)
    return state, game


def open_checkin():
    return AppTest.from_file(ROOT / "pages/3_Check_in.py", default_timeout=10).run()


def set_location(page, state, accuracy_m=10, age_seconds=0):
    """Simulate the phone reporting a position inside TERRITORY."""
    state["location"] = {"lat": INSIDE[0], "lng": INSIDE[1], "accuracy_m": accuracy_m,
                         "taken_at_ms": (time.time() - age_seconds) * 1000}
    page.run()


def gate(page):
    """Text of the 'check-in not open' card shown instead of the camera."""
    return "".join(item.value for item in page.markdown if 'gate-card' in item.value)


def reward(page):
    """Text of the check-in reward card (empty when none is shown)."""
    return "".join(item.value for item in page.markdown if 'class="reward-card"' in item.value)


def test_quick_controls_preview_save_and_owner_income(ui):
    state, game = ui
    page = open_checkin()
    assert not page.exception
    assert radio(page, "Drink").options == ["Beer", "Wine", "Shot", "Mixed drink"]
    assert radio(page, "Size").options == ["Small 250 ml", "Medium 330 ml", "Large 500 ml"]
    radio(page, "Drink").set_value("wine").run()
    radio(page, "Size").set_value("large").run()
    assert any("+4 points" in item.value for item in page.info)
    set_location(page, state)
    button(page, "Submit").click().run()
    assert not page.exception and 'reward-points">+4<' in reward(page)
    assert state["entries"][0].points_awarded == 4
    assert state["entries"][0].size == "large" and state["entries"][0].amount == 250
    assert state["calls"] == 1
    assert "owner also earned +1 season points" in reward(page)


def test_shot_skips_size_and_mixed_uses_labels(ui):
    page = open_checkin()
    radio(page, "Drink").set_value("shot").run()
    assert not any(item.label == "Size" for item in page.radio)
    assert any("+4 points" in item.value for item in page.info)
    # The size row keeps its place for a shot (invisible spacer + min-height), so the photo does not jump.
    assert any('class="size-spacer"' in m.value for m in page.markdown)
    css = (ROOT / "assets" / "drink_entries.css").read_text(encoding="utf-8")
    assert ".st-key-drink_ui_sizes { min-height: 40px; }" in css and ".size-spacer { display: block; height: 0;" in css
    radio(page, "Drink").set_value("mixed").run()
    assert not any('class="size-spacer"' in m.value for m in page.markdown), "a drink with sizes shows the radio, not the spacer"
    assert radio(page, "Size").options == ["Small", "Medium", "Large"]


def test_time_duel_boost_is_in_the_checkin_preview(ui, monkeypatch):
    monkeypatch.setattr(db, 'time_status', lambda *args: {'boost_ends_at': (START + timedelta(hours=1)).isoformat()})
    page = open_checkin()
    radio(page, 'Size').set_value('large').run()
    assert not page.exception
    assert any('Time Duel ×1.25 until' in item.value for item in page.success)
    assert any('+3.75 points' in item.value for item in page.info)


def test_checkin_form_has_only_the_necessary_controls_and_little_text(ui):
    state, _ = ui
    page = open_checkin()
    set_location(page, state)
    assert [b.label for b in page.button] == ["Profile", "Lobbies", "Map", "Ranks", "Check in", "Games", "Photos", "Retake photo", "Submit"] \
        or [b.label for b in page.button][-2:] == ["Retake photo", "Submit"]
    assert len([b for b in page.button if b.label not in {"Profile", "Lobbies", "Map", "Ranks", "Check in", "Games", "Photos"}]) == 2
    text = " ".join(m.value for m in page.markdown) + " ".join(c.value for c in page.caption)
    for gone in ("Take a photo. Choose your drink", "Looking good", "Shared only with your lobby", "One drink, one size",
                 "Preview only", "territory points if", "25% season income", "Your location assigns"):
        assert gone not in text, gone


def test_camera_photo_is_required_before_selecting_drink_or_size(ui):
    state, _ = ui
    captured = state["photo"]
    state["photo"] = None
    page = open_checkin()
    assert not page.exception
    assert not page.radio and not any(item.label == "Submit" for item in page.button)
    assert 'checkin_pending_photo' not in page.session_state
    state["photo"] = captured
    page.run()
    assert not page.exception and radio(page, "Drink") and radio(page, "Size")


def test_capture_unmounts_camera_and_retake_opens_fresh_camera(ui, monkeypatch):
    state, _ = ui
    camera = Mock(side_effect=lambda key: state['photo'] if key.endswith('_0') else None)
    monkeypatch.setattr('camera_capture.camera_photo', camera)
    page = open_checkin()
    assert camera.call_count == 1 and len(page.get('html')) == 1
    capture = page.session_state['checkin_capture'][1]
    radio(page, 'Drink').set_value('wine').run()
    assert camera.call_count == 1, 'Details reruns must not remount a stopped camera'
    assert page.session_state['checkin_capture'][1] == capture
    button(page, 'Retake photo').click().run()
    assert camera.call_count == 2
    assert camera.call_args.kwargs['key'] == 'checkin_photo_1'
    assert 'checkin_capture' not in page.session_state and 'checkin_pending_photo' not in page.session_state
    assert not page.radio and not page.get('html') and state['calls'] == 0


def test_success_does_not_reopen_camera_and_plus_starts_new_capture(ui, monkeypatch):
    state, _ = ui
    camera = Mock(side_effect=lambda key: state['photo'] if key.endswith('_0') else None)
    monkeypatch.setattr('camera_capture.camera_photo', camera)
    page = open_checkin()
    set_location(page, state)
    button(page, 'Submit').click().run()
    assert not page.exception and reward(page)
    assert camera.call_count == 1 and 'checkin_pending_photo' not in page.session_state
    assert not page.radio and button(page, 'Go to map') and not any(b.label == 'New check-in' for b in page.button)
    assert [b.label for b in page.button if b.label not in {"Profile", "Lobbies", "Map", "Ranks", "Check in", "Games", "Photos"}] == ["Go to map"]
    # Straight after a check-in the cooldown runs: + shows the countdown, not the camera.
    page.session_state['checkin_open_camera'] = True
    page.run()
    assert not page.exception and camera.call_count == 1 and 'Next check-in in' in gate(page)
    state['now'] = state['now'] + timedelta(seconds=120)
    button(page, 'Check again').click().run()
    assert not page.exception and camera.call_count == 2 and not page.radio


def test_checkin_form_is_one_screen_the_photo_fills_the_free_space(ui):
    state, _ = ui
    page = open_checkin()
    set_location(page, state)
    assert any(b.key == "checkin_retake" for b in page.button), "Retake is a round button on the photo"
    keys = [b.key for b in page.button]
    assert keys.index("checkin_retake") < len(keys) - 1
    html = "\n".join(item.value for item in page.get("html"))
    assert 'class="checkin-photo"' in html
    css = (ROOT / "assets" / "drink_entries.css").read_text(encoding="utf-8")
    # The photo wrapper is the only flex child that may grow or shrink; the page cannot scroll.
    assert "has(> .st-key-checkin_photo) { flex: 1 1 0" in css
    assert "height: 100dvh" in css and "flex-shrink: 0" in css
    # One location line with the territory, no separate territory row.
    assert any("Location found, accurate to 10 m" in c.value for c in page.caption)
    assert not any("Territory" == m.value for m in page.markdown)


def test_go_to_map_is_the_one_button_after_a_checkin_and_leaves_a_clean_checkin_page(ui, monkeypatch):
    from unittest.mock import Mock
    import streamlit as st
    state, _ = ui
    switch = Mock()
    monkeypatch.setattr(st, "switch_page", switch)
    page = open_checkin()
    set_location(page, state)
    button(page, "Submit").click().run()
    assert page.session_state["checkin_posted"] is True
    button(page, "Go to map").click().run()
    assert switch.call_args.args == ("pages/5_Map.py",)
    assert "checkin_posted" not in page.session_state, "coming back to Check-in must not show the old result"


def test_changing_context_discards_pending_photo(ui, monkeypatch):
    state, _ = ui
    page = open_checkin()
    monkeypatch.setattr('shared.require_active_membership', lambda: ('another-member', 'lobby', 'season'))
    page.run()
    assert not page.exception and 'checkin_pending_photo' not in page.session_state
    assert not page.radio and state['calls'] == 0


def test_closing_camera_saves_nothing(ui, monkeypatch):
    from camera_capture import CameraCancelled
    state, _ = ui
    monkeypatch.setattr('camera_capture.camera_photo', Mock(side_effect=CameraCancelled))
    switch = Mock()
    monkeypatch.setattr(st, 'switch_page', switch)
    page = open_checkin()
    assert not page.exception and state['calls'] == 0 and not page.radio
    switch.assert_called_once_with('pages/2_Lobby.py')


def test_location_starts_before_camera_capture(ui, monkeypatch):
    state, _ = ui
    state['photo'] = None
    tracking = Mock(return_value=None)
    monkeypatch.setattr('phone_location._phone_location', tracking)
    page = open_checkin()
    assert not page.exception and tracking.called
    assert not any(item.label == 'Submit' for item in page.button)


def test_outside_window_shows_next_opening_before_the_camera(ui, monkeypatch):
    state, _ = ui
    camera = Mock(return_value=state["photo"])
    monkeypatch.setattr('camera_capture.camera_photo', camera)
    state["now"] = START + timedelta(days=3)
    page = open_checkin()
    assert not page.exception and camera.call_count == 0
    card = gate(page)
    assert "Game night opens" in card and "Europe/Lisbon" in card
    assert not any(b.label == "Submit" for b in page.button) and button(page, "Check again")
    assert state["entries"] == []


def test_window_closing_after_the_photo_still_blocks_submission(ui):
    state, _ = ui
    page = open_checkin()
    set_location(page, state)
    state["now"] = START + timedelta(days=3)
    page.run()
    assert not page.exception
    assert_blocked(page, "Submit", "Scoring is closed", "Refresh")
    assert any("Scoring is closed" in item.value and "Europe/Lisbon" in item.value for item in page.warning)
    assert state["entries"] == []


def test_cooldown_shows_countdown_instead_of_the_camera(ui, monkeypatch):
    state, _ = ui
    camera = Mock(return_value=state["photo"])
    monkeypatch.setattr('camera_capture.camera_photo', camera)
    state["now"] = START + timedelta(seconds=60)
    state["entries"] = [entry("saved", "member", "shot", None, 0)]
    page = open_checkin()
    assert not page.exception and camera.call_count == 0
    assert "1:00" in gate(page) and "every 2 minutes" in gate(page)
    state["now"] = START + timedelta(seconds=120)
    button(page, "Check again").click().run()
    assert not page.exception and camera.call_count == 1


def test_cooldown_keeps_capture_and_selection_and_expires_at_two_minutes(ui):
    # A photo taken before the cooldown started (e.g. a check-in from another
    # device) is kept, with the wait shown under it.
    state, _ = ui
    state["now"] = START + timedelta(seconds=60)
    page = open_checkin()
    state["entries"] = [entry("saved", "member", "shot", None, 0)]
    set_location(page, state)
    capture = page.session_state["checkin_capture"][1]
    radio(page, "Drink").set_value("mixed").run()
    assert_blocked(page, "Submit", "1:00", "wait")
    assert any("Next check-in in 1:00" in item.value for item in page.warning)
    assert page.session_state["checkin_capture"][1] == capture
    state["now"] = START + timedelta(seconds=120)
    button(page, "Refresh remaining wait").click().run()
    assert not button(page, "Submit").disabled
    assert radio(page, "Drink").value == "mixed"
    assert page.session_state["checkin_capture"][1] == capture
    assert state["calls"] == 0


def test_lost_save_reply_recovers_without_a_second_award(ui):
    state, _ = ui
    state["lose_reply"] = True
    page = open_checkin()
    set_location(page, state)
    button(page, "Submit").click().run()
    assert not page.exception and page.error
    assert state["calls"] == 1 and len(state["entries"]) == 1
    page.run()
    assert not page.exception and 'reward-points">+1<' in reward(page)
    assert state["calls"] == 1 and len(state["entries"]) == 1


@pytest.mark.parametrize('previous_member,previous_size,captured', [
    (None, None, True), ('rival', 'medium', True),
    ('rival', 'large', False), ('member', 'medium', False),
])
def test_saved_checkin_shows_only_actual_capture(ui, monkeypatch, previous_member, previous_size, captured):
    state, _ = ui
    monkeypatch.setattr(db, 'membership_display_name', lambda *args: 'Leo')
    if previous_member:
        state['entries'] = [entry('prior', previous_member, 'beer', previous_size, -4, order=1)]
    page = open_checkin()
    set_location(page, state)
    radio(page, 'Size').set_value('large').run()
    assert not reward(page)
    button(page, 'Submit').click().run()
    assert not page.exception and state['calls'] == 1
    assert 'reward-points">+3<' in reward(page)
    assert (f'You captured {TERRITORY.name}!' in reward(page)) is captured
    assert f'in {TERRITORY.name}' in reward(page)
    page.run()
    assert 'You captured' not in reward(page)


def test_capture_message_recovers_after_lost_save_reply(ui):
    state, _ = ui
    state['lose_reply'] = True
    page = open_checkin()
    set_location(page, state)
    button(page, 'Submit').click().run()
    assert page.error and state['calls'] == 1
    page.run()
    assert not page.exception and state['calls'] == 1
    assert f'You captured {TERRITORY.name}!' in reward(page)


def test_capture_lookup_failure_preserves_saved_confirmation(ui, monkeypatch):
    state, _ = ui
    def history(_):
        if state['calls']:
            raise ReadTimeout('History unavailable after save')
        return []
    monkeypatch.setattr(db, 'list_drink_entries', history)
    page = open_checkin()
    set_location(page, state)
    button(page, 'Submit').click().run()
    assert not page.exception and state['calls'] == 1
    assert 'reward-points">+1<' in reward(page)
    assert 'ownership update is unavailable' in reward(page)
    assert 'You captured' not in reward(page)


def test_history_correction_replays_and_survives_new_ui_session(ui, monkeypatch):
    state, game = ui
    model = entry("original", "member", "wine", "large", 0)
    state["now"] = START + timedelta(seconds=60)
    data = {"model": model}

    def photos(player,lobby):
        model = data["model"]
        return [{"id": model.id, "username": "Mia", "captured_at": None, "submitted_at": model.submitted_at.isoformat(),
            "is_owner": True, "has_photo": False, "timezone_name": game.timezone_name, "rule_version": "v1",
            "entry": model, "season": game, "corrected_at": model.corrected_at.isoformat() if model.corrected_at else None,
            "income_recipient": "Leo", "location": "matched", "territory": TERRITORY.name}]
    def correct(player,lobby,entry_id,kind,size,revision):
        assert revision == data["model"].revision
        data["model"] = rules.corrected_entry(data["model"],game,kind,size,state["now"])
        return data["model"]
    monkeypatch.setattr(db, "list_checkin_photos", photos)
    monkeypatch.setattr(db, "download_checkin_photo", lambda *args: None)
    monkeypatch.setattr(db, "correct_checkin", correct)
    monkeypatch.setattr(db, "list_checkin_revisions", lambda *args: [{"revision": 1,"old_drink_type":"wine","old_size":"large",
        "new_drink_type":"wine","new_size":"small","corrected_at":state["now"].isoformat()}])
    page = AppTest.from_file(ROOT / "pages/6_Check_in_photos.py", default_timeout=10).run()
    assert not page.exception
    assert_blocked(page, "Save correction", "unchanged", "choose")
    assert any("+4 season" in item.value for item in page.text)
    radio(page, "Correct size").set_value("small").run()
    button(page, "Save correction").click().run()
    assert not page.exception
    assert any("recalculated" in item.value for item in page.success)
    assert any("+1 season" in item.value for item in page.text)
    fresh = AppTest.from_file(ROOT / "pages/6_Check_in_photos.py", default_timeout=10).run()
    assert not fresh.exception and any("+1 season" in item.value for item in fresh.text)
    assert fresh.table and "100 ml" in next(item.value for item in fresh.text if "Wine" in item.value)


@pytest.mark.parametrize("boost_enabled", [False, True])
def test_modern_save_sends_selection_but_never_client_point_awards(monkeypatch, boost_enabled):
    model = replace(entry("capture", "member", "beer", "large", 0), photo_captured_at=START)
    game = season()
    if not boost_enabled:
        game.scoring_rules.pop("territory_boost")
    monkeypatch.setattr(db, "list_memberships_for_player", lambda _: [type("M",(),{"id":"member","lobby_id":"lobby"})()])
    monkeypatch.setattr(db, "list_seasons_for_lobby", lambda _: [game])
    monkeypatch.setattr("data.territory_file.boost_candidate_ids", lambda origin, _: [origin, "neighbor"])
    client = Mock()
    client.storage.get_bucket.return_value.public = False
    query = client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value.data = []
    row = db._drink_entry_row(replace(model, points_awarded=3))
    client.rpc.return_value.execute.return_value.data = [row]
    monkeypatch.setattr(db, "get_client", lambda: client)
    saved = db.save_drink_entry_photo("player","lobby",replace(model,points_awarded=999),b"clean")
    assert saved.points_awarded == 3
    name, parameters = client.rpc.call_args.args
    if boost_enabled:
        assert name == "accept_territory_scoring_checkin"
        assert parameters["reachable_territories"] == [model.territory_id, "neighbor"]
    else:
        assert name == "accept_scoring_checkin"
        assert "reachable_territories" not in parameters
    assert parameters["selected_size"] == "large"
    assert not any("points" in key or "bonus" in key for key in parameters)
    client.table.return_value.upsert.assert_not_called()


@pytest.mark.parametrize('test_mode', [False, True])
def test_new_lobby_starts_versioned_season_in_chosen_timezone(monkeypatch, test_mode):
    from core.lobbies import create_season
    members, games, calls, lobbies = [], [], [], []
    monkeypatch.setattr("shared.require_login", lambda: "player")
    monkeypatch.setattr("shared.show_logged_in_as", lambda: None)
    monkeypatch.setattr(db, "pending_lobby_invitations", lambda _: [])
    monkeypatch.setattr(db,"list_memberships_for_player",lambda _, **kwargs: list(members))
    monkeypatch.setattr(db,"insert_lobby",lobbies.append)
    monkeypatch.setattr(db,"list_lobbies",lambda:list(lobbies))
    monkeypatch.setattr(db,"list_drink_entries",lambda _:[])
    monkeypatch.setattr(db,"insert_membership",members.append)
    monkeypatch.setattr(db,"list_seasons_for_lobby",lambda _:list(games))
    def start(player,lobby,length,zone, **options):
        calls.append((player,lobby,length,zone))
        game=create_season(lobby,length,datetime.now(timezone.utc),zone, **options)
        games.append(game)
        return game
    monkeypatch.setattr(db,"start_scoring_season",start)
    monkeypatch.setattr(db,"list_memberships_for_lobby",lambda _, **kwargs: list(members))
    monkeypatch.setattr(db,"list_public_usernames",lambda: [{"id": "player", "display_name": "Player"}])
    monkeypatch.setattr(db,"list_friendships",lambda _:[])
    page=AppTest.from_file(ROOT/"pages/2_Lobby.py", default_timeout=10).run()
    next(item for item in page.button if item.key == "open_create_lobby").click().run()
    next(item for item in page.text_input if item.label=="Lobby name").input("New friends")
    next(item for item in page.selectbox if item.label=="Lobby timezone").set_value("America/New_York")
    next(item for item in page.checkbox if item.key == 'create_test_season').set_value(test_mode)
    [b for b in page.button if b.label == "Create lobby"][-1].click().run()
    assert not page.exception
    assert games[0].scoring_version=="v1" and games[0].timezone_name=="America/New_York"
    assert games[0].scoring_rules["points"]["shot"]["standard"]==4
    assert bool(games[0].scoring_rules.get('test_mode')) is test_mode
    assert games[0].scoring_rules['start_weekday'] == (2 if test_mode else 3)
    assert calls[0][0]=="player" and page.session_state["current_season_id"]==games[0].id


def test_removed_membership_stops_before_game_records_are_loaded(monkeypatch):
    monkeypatch.setattr("shared.require_login",lambda:"player")
    monkeypatch.setattr("shared.show_logged_in_as",lambda:None)
    monkeypatch.setattr(db,"membership_context",lambda *args:(None, None))
    records=Mock()
    monkeypatch.setattr(db,"list_drink_entries",records)
    page=AppTest.from_file(ROOT/"pages/4_Standings.py", default_timeout=10)
    for key,value in {"player_id":"player","current_membership_id":"removed","current_lobby_id":"lobby","current_season_id":"season"}.items():
        page.session_state[key]=value
    page.run()
    assert not page.exception and any("membership is no longer" in item.value for item in page.error)
    records.assert_not_called()


def test_history_memories_group_by_game_night_and_open_the_tapped_entry(ui, monkeypatch):
    state, game = ui
    # Three game nights: the newest two hold one photo each, the oldest holds
    # two -- newest-first, matching db.list_checkin_photos's own order.
    models = [entry("photo-3", "member", "beer", "small", 14 * 24 * 60),
              entry("photo-2", "member", "beer", "small", 7 * 24 * 60),
              entry("photo-1", "member", "beer", "small", 5),
              entry("photo-0", "member", "beer", "small", 0)]
    photos = [{"id": model.id, "username": "Mia", "captured_at": None,
               "submitted_at": model.submitted_at.isoformat(), "is_owner": True,
               "has_photo": True, "timezone_name": game.timezone_name, "rule_version": "v1",
               "entry": model, "season": game, "corrected_at": None, "income_recipient": None,
               "location": "matched", "territory": TERRITORY.name} for model in models]
    photos[0]["username"] = '<img src=x onerror="alert(1)">'
    downloads = []
    monkeypatch.setattr(db, "list_checkin_photos", lambda *args: photos)
    def download(player, lobby, entry_id):
        assert (player, lobby) == ("player", "lobby")
        downloads.append(entry_id)
        return state["photo"].getvalue()
    monkeypatch.setattr(db, "download_checkin_photo", download)
    page = AppTest.from_file(ROOT / "pages/6_Check_in_photos.py", default_timeout=10).run()
    assert not page.exception

    # One continuous list: all three game nights at once, every photo fetched on its own.
    assert sorted(downloads) == ["photo-0", "photo-1", "photo-2", "photo-3"]
    markup = "\n".join(item.value for item in page.markdown)
    assert markup.count("Game night") == 3
    tiles = "\n".join(item.value for item in page.get("html"))
    assert "&lt;img" in tiles and photos[0]["username"] not in tiles
    assert not any(b.label in {"Newer photos", "Older photos", "Load more"} for b in page.button), "nothing left to page through"

    next(b for b in page.button if b.key == "memory_tile_photo-0_open").click().run()
    assert not page.exception
    assert page.session_state["history_detail_id"] == "photo-0"
    assert any("Mia" in item.value for item in page.text)

    button(page, "Back to photos").click().run()
    assert not page.exception
    assert "history_detail_id" not in page.session_state
    assert any(b.key == "memory_tile_photo-0_open" for b in page.button)


def test_photos_grid_shows_name_and_points_and_mine_hides_other_players(ui, monkeypatch):
    state, game = ui
    models = [entry("theirs", "other", "beer", "small", 2), entry("mine", "member", "beer", "small", 1)]
    photos = [{"id": model.id, "username": name, "captured_at": None, "submitted_at": model.submitted_at.isoformat(),
               "is_owner": owner, "has_photo": True, "timezone_name": game.timezone_name, "rule_version": "v1",
               "entry": model, "season": game, "corrected_at": None, "income_recipient": None,
               "location": "matched", "territory": TERRITORY.name}
              for model, name, owner in zip(models, ["Leo", "Mia"], [False, True])]
    downloads = []
    monkeypatch.setattr(db, "list_checkin_photos", lambda *args: photos)
    monkeypatch.setattr(db, "download_checkin_photo", lambda p, l, entry_id: downloads.append(entry_id) or state["photo"].getvalue())
    page = AppTest.from_file(ROOT / "pages/6_Check_in_photos.py", default_timeout=10).run()
    assert not page.exception
    tiles = "\n".join(item.value for item in page.get("html"))
    assert tiles.count('class="memory-tile-visual"') == 2
    assert "<span>Leo</span><b>+1</b>" in tiles and "<span>Mia</span><b>+1</b>" in tiles
    assert sorted(downloads) == ["mine", "theirs"]
    page.radio(key="photo_filter").set_value("Mine").run()
    assert not page.exception
    tiles = "\n".join(item.value for item in page.get("html"))
    assert tiles.count('class="memory-tile-visual"') == 1 and "Leo" not in tiles
    assert any("Photos stay until" in item.value for item in page.caption)


def test_gallery_access_denial_stops_before_rendering_a_photo(ui, monkeypatch):
    _, game = ui
    models = [entry(f"photo-{i}", "member", "beer", "small", i) for i in range(2)]
    stubs = [{"id": model.id, "submitted_at": model.submitted_at.isoformat(), "captured_at": None,
              "timezone_name": game.timezone_name, "season": game} for model in models]
    monkeypatch.setattr(db, "list_checkin_photos", lambda *args: stubs)
    def denied(*args):
        raise PermissionError("Membership revoked")
    monkeypatch.setattr(db, "download_checkin_photo", denied)
    page = AppTest.from_file(ROOT / "pages/6_Check_in_photos.py", default_timeout=10).run()
    assert not page.exception and page.warning
    assert not page.get("html")


def test_busy_history_loads_24_then_more_and_every_photo_keeps_its_own_access_check(ui,monkeypatch):
    state,game=ui
    models=[entry(f'busy-{i}','member','beer','small',i) for i in range(25)]
    photos=[dict(id=m.id,username='Mia',captured_at=None,submitted_at=m.submitted_at.isoformat(),
        is_owner=True,has_photo=True,timezone_name=game.timezone_name,rule_version='v1',
        entry=m,season=game,corrected_at=None,income_recipient=None,location='matched',territory=TERRITORY.name)
        for m in reversed(models)]
    calls=[]
    monkeypatch.setattr(db,'list_checkin_photos',lambda *args:photos)
    def download(*args):
        calls.append(args)
        return state['photo'].getvalue()
    monkeypatch.setattr(db,'download_checkin_photo',download)
    page=AppTest.from_file(ROOT/'pages/6_Check_in_photos.py').run()
    assert not page.exception and {c[-1] for c in calls}=={f'busy-{i}' for i in range(1,25)}
    assert len(calls)==24, 'Only the first 24 photos are fetched'
    assert all(c[:2]==('player','lobby') for c in calls), 'Every fetch carries the viewer and the lobby, so the server checks access per photo'
    assert any('24 of 25 photos' in c.value for c in page.caption)
    before=len(calls)
    button(page,'Load more').click().run()
    assert not page.exception and len(calls)-before==25, 'Every photo is checked again on each load (no cached bytes)'
    assert {c[-1] for c in calls[before:]}=={f'busy-{i}' for i in range(25)}
    assert not any(b.label=='Load more' for b in page.button), 'All photos are listed now'
    before=len(calls)
    next(b for b in page.button if b.key=='memory_tile_busy-1_open').click().run()
    assert not page.exception and [c[-1] for c in calls[before:]]==['busy-1'],'Opening a detail must not reload the gallery'


def test_more_photos_than_one_batch_are_fetched_in_slices_of_twelve(ui,monkeypatch):
    """Production error: the list asked for 24 photos in one call, the batch function allows 12."""
    state,game=ui
    models=[entry(f'big-{i}','member','beer','small',i) for i in range(30)]
    photos=[dict(id=m.id,username='Mia',captured_at=None,submitted_at=m.submitted_at.isoformat(),
        is_owner=True,has_photo=True,timezone_name=game.timezone_name,rule_version='v1',
        entry=m,season=game,corrected_at=None,income_recipient=None,location='matched',territory=TERRITORY.name)
        for m in reversed(models)]
    sizes=[]
    monkeypatch.setattr(db,'list_checkin_photos',lambda *args:photos)
    def batch(p,l,ids):
        sizes.append(len(ids))
        assert p=='player' and l=='lobby'
        if len(ids)>12:
            raise ValueError('Load at most twelve check-in photos at once.')   # what the real function does
        return {i:state['photo'].getvalue() for i in ids}
    monkeypatch.setattr(db,'download_checkin_photos',batch)
    page=AppTest.from_file(ROOT/'pages/6_Check_in_photos.py').run()
    assert not page.exception and sizes==[12,12], 'The first 24 photos go out as two fresh batches of 12'
    assert sum('base64' in h.value for h in page.get('html'))==24, 'All 24 photos are shown'
    sizes.clear()
    button(page,'Load more').click().run()
    assert not page.exception and sizes==[12,12,6], 'All 30 photos as 12 + 12 + 6, each batch authorized on its own'


def test_a_failed_batch_only_hides_its_own_photos_and_lost_access_stops_the_page(ui,monkeypatch):
    state,game=ui
    models=[entry(f'f-{i}','member','beer','small',i) for i in range(20)]
    photos=[dict(id=m.id,username='Mia',captured_at=None,submitted_at=m.submitted_at.isoformat(),
        is_owner=True,has_photo=True,timezone_name=game.timezone_name,rule_version='v1',
        entry=m,season=game,corrected_at=None,income_recipient=None,location='matched',territory=TERRITORY.name)
        for m in reversed(models)]
    monkeypatch.setattr(db,'list_checkin_photos',lambda *args:photos)
    def flaky(p,l,ids):
        if 'f-19' in ids:                      # the newest slice fails
            raise RuntimeError('storage unavailable')
        return {i:state['photo'].getvalue() for i in ids}
    monkeypatch.setattr(db,'download_checkin_photos',flaky)
    page=AppTest.from_file(ROOT/'pages/6_Check_in_photos.py').run()
    assert not page.exception and any('could not be loaded' in w.value for w in page.warning)
    assert sum('base64' in h.value for h in page.get('html'))==8, 'The 8 photos of the other slice still show'
    def revoked(p,l,ids):
        raise PermissionError('Membership revoked')
    monkeypatch.setattr(db,'download_checkin_photos',revoked)
    page=AppTest.from_file(ROOT/'pages/6_Check_in_photos.py').run()
    assert not page.exception and any('Photo access changed' in w.value for w in page.warning)
    assert not any('base64' in h.value for h in page.get('html')), 'Lost access shows no photo at all'


def test_changing_the_filter_starts_again_at_the_newest_photos(ui,monkeypatch):
    state,game=ui
    models=[entry(f'p-{i}','member' if i%2 else 'other','beer','small',i) for i in range(60)]
    photos=[dict(id=m.id,username='Mia',captured_at=None,submitted_at=m.submitted_at.isoformat(),
        is_owner=m.membership_id=='member',has_photo=True,timezone_name=game.timezone_name,rule_version='v1',
        entry=m,season=game,corrected_at=None,income_recipient=None,location='matched',territory=TERRITORY.name)
        for m in reversed(models)]
    calls=[]
    monkeypatch.setattr(db,'list_checkin_photos',lambda *args:photos)
    monkeypatch.setattr(db,'download_checkin_photo',lambda *args:calls.append(args[-1]) or state['photo'].getvalue())
    page=AppTest.from_file(ROOT/'pages/6_Check_in_photos.py').run()
    button(page,'Load more').click().run()
    assert page.session_state['history_shown']==48
    page.radio(key='photo_filter').set_value('Mine').run()
    assert not page.exception and page.session_state['history_shown']==24
    assert any('24 of 30 photos' in c.value for c in page.caption)


def test_submit_needs_the_phone_location_first(ui):
    state, _ = ui
    page = open_checkin()
    assert_blocked(page, "Submit", "location", "allow")
    assert any("Finding your location" in item.value for item in page.caption)
    set_location(page, state)
    assert not button(page, "Submit").disabled
    assert any("Location found, accurate to 10 m" in item.value for item in page.caption)


def test_inaccurate_phone_location_warns_and_saves_nothing(ui):
    state, _ = ui
    page = open_checkin()
    set_location(page, state, accuracy_m=80)
    assert any("only accurate to about 80 m" in item.value for item in page.warning)
    button(page, "Submit").click().run()
    assert not page.exception and any("80 m" in item.value and "50 m" in item.value for item in page.error)
    assert state["calls"] == 0 and state["entries"] == []


def test_phone_permission_retry_keeps_photo_and_selection_and_accepts_50m(ui):
    state, _ = ui
    page = open_checkin()
    capture_id = page.session_state["checkin_capture"][1]
    radio(page, "Drink").set_value("wine").run()
    radio(page, "Size").set_value("large").run()
    state["location"] = {"error": "denied"}
    page.run()
    assert not page.exception
    assert_blocked(page, "Submit", "blocked", "browser settings")
    assert any("Location is blocked" in item.value for item in page.warning)
    assert page.session_state["checkin_capture"][1] == capture_id
    assert radio(page, "Drink").value == "wine" and radio(page, "Size").value == "large"
    assert state["calls"] == 0 and state["entries"] == []
    set_location(page, state, accuracy_m=50)
    assert not button(page, "Submit").disabled
    button(page, "Submit").click().run()
    assert not page.exception and state["calls"] == 1
    assert state["entries"][0].id == capture_id and state["entries"][0].points_awarded == 4


def test_location_older_than_60_seconds_is_not_used(ui):
    """R-L04: a reading must be fresh; 61 s old blocks Submit, 59 s is fine."""
    state, _ = ui
    page = open_checkin()
    set_location(page, state, age_seconds=61)
    assert_blocked(page, "Submit", "60 seconds", "fresh reading")
    assert any("Updating your location" in item.value for item in page.caption)
    set_location(page, state, age_seconds=59)
    assert not button(page, "Submit").disabled
