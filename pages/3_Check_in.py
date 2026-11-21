"""Log a drink with a required camera photo and the phone's GPS.

The location is followed automatically while the page is open
(phone_location.py): the newest phone GPS reading is used if it is at most
60 s old and accurate to 50 m (R-L01, R-L02, R-L04). Photo GPS is not used.
"""

from base64 import b64encode
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from uuid import uuid4

import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError
from storage3.utils import StorageException

import data.db as db
from action_feedback import action_button, explain, service_error
from core.action_feedback import AMBIGUOUS_TERRITORY_MESSAGE, checkin_message, location_problem as location_blocker
from camera_capture import CameraCancelled, camera_photo
from core.checkin_photo import InvalidCheckinPhoto, prepare_checkin_photo
from core.checkins import CheckinRejected, create_drink_entry
from core.checkin_feedback import captured_territory
from core.scoring_v1 import (DRINK_LABELS, SIZE_LABELS, TERRITORY_MULTIPLIER, base_points, cooldown_remaining,
    create_scored_entry, current_time, format_points, next_opening, rules_for, scoring_open, size_label, utc)
from core.constants import MAX_GPS_ACCURACY_M
from core.location import evaluate_location
from drink_entry_ui import gate_card_html, page_header, reward_card_html
from phone_location import current_location, track_location
from shared import get_territories, lobby_button, require_active_membership, require_login, selected_season, show_logged_in_as

player_id = require_login()
show_logged_in_as()
membership_id, lobby_id, season_id = require_active_membership()

season = selected_season(lobby_id, season_id)
if season is None:
    st.info("Open Lobbies and finish the selected lobby's setup, or make another active lobby current before checking in.")
    lobby_button()
    st.stop()
modern = season.scoring_version == "v1"
rules = rules_for(season) if modern else None
team_mode = st.session_state.get("current_lobby_mode") == "team"
competitor_id = st.session_state.get("current_team_id") if team_mode else membership_id
if team_mode and not competitor_id:
    st.info("Open this lobby on the Lobby page and join a team before checking in.")
    lobby_button()
    st.stop()
now = current_time()
try:
    recent_entries = db.list_drink_entries_for_membership(membership_id)
except (APIError, RequestError, RuntimeError, OSError):
    st.error("Your recent check-ins could not be loaded, so we cannot check the cooldown safely. Reload Check in to try again.")
    st.stop()
track_location()


def reset_camera():
    """Forget an unsaved capture; a new component key opens a fresh stream."""
    for key in ('checkin_pending_photo', 'checkin_capture', 'checkin_posted', 'checkin_saved_result'):
        st.session_state.pop(key, None)
    st.session_state['checkin_photo_number'] = st.session_state.get('checkin_photo_number', -1) + 1


def finish_checkin(entry):
    reset_camera()
    st.session_state['checkin_posted'] = True
    st.session_state['checkin_saved_result'] = (entry.points_awarded + entry.time_bonus, entry.location_check_result,
                                               entry.owner_bonus_quarters, entry.id)
    st.rerun()


context = (player_id, membership_id, season_id)
if st.session_state.get('checkin_context') != context:
    reset_camera()
    st.session_state['checkin_context'] = context
if st.session_state.pop('checkin_open_camera', False):
    reset_camera()
photo_number = st.session_state.get('checkin_photo_number', 0)
photo = st.session_state.get('checkin_pending_photo')

# Check the window and the cooldown before the camera opens, so nobody takes
# a photo that can't count. A photo already taken keeps the warnings below.
period_closed = not utc(season.starts_at) <= utc(now) < utc(season.ends_at)
closed = period_closed or (modern and not scoring_open(now, season))
waiting = cooldown_remaining(membership_id, now, recent_entries, rules["cooldown_seconds"]) if modern else 0
if photo is None and not st.session_state.get('checkin_posted') and (closed or waiting):
    page_header("Check in", compact=True)
    zone = ZoneInfo(season.timezone_name)
    opening = next_opening(now, season) if closed and modern else None
    if waiting and not closed:
        card = gate_card_html("Next check-in in", f"{waiting // 60}:{waiting % 60:02d}",
                              f"One drink every {rules['cooldown_seconds'] // 60} minutes.")
    elif opening:
        local = opening.astimezone(zone)
        card = gate_card_html("Game night opens", f"{local:%a %H:%M}",
                              f"Check-ins open {local:%A %d %B at %H:%M} ({season.timezone_name}).")
    elif utc(now) < utc(season.starts_at):
        local = season.starts_at.astimezone(zone)
        card = gate_card_html("Season starts", f"{local:%d %b}", f"{local:%A %d %B at %H:%M} ({season.timezone_name}).")
    else:
        card = gate_card_html("Season over", "Done", "Create or join a new lobby on the Lobbies page and make it current to play again.")
    st.markdown(card, unsafe_allow_html=True)
    if closed and not opening and not utc(now) < utc(season.starts_at):
        lobby_button()
    elif st.button("Check again", type="primary", width="stretch"):
        st.rerun()
    st.stop()

if photo is None and not st.session_state.get('checkin_posted'):
    # Only the camera occupies the viewport. GPS continues in its hidden component.
    st.markdown("""<style>
      .st-key-checkin_camera_stage {position:fixed!important;inset:0;z-index:100000;
        width:100vw!important;max-width:none!important;background:var(--bg,#1A2841);overflow:hidden;}
      .st-key-checkin_camera_stage iframe {width:100vw!important;height:100dvh!important;border:0;}
      body:has(.st-key-checkin_camera_stage) [data-testid="stHeader"],
      body:has(.st-key-checkin_camera_stage) [data-testid="stSidebar"],
      body:has(.st-key-checkin_camera_stage) .st-key-wego_bottom_nav {display:none!important;}
      .st-key-checkin_camera_error {position:fixed;top:90px;left:20px;right:20px;z-index:100001;}
    </style>""", unsafe_allow_html=True)
    with st.container(key='checkin_camera_stage'):
        try:
            photo = camera_photo(key=f'checkin_photo_{photo_number}')
        except CameraCancelled:
            reset_camera()
            st.switch_page('pages/2_Lobby.py')
            st.stop()
        except InvalidCheckinPhoto as error:
            with st.container(key='checkin_camera_error'):
                st.error(str(error))
                if st.button('Try camera again'):
                    reset_camera()
                    st.rerun()
            st.stop()
    if photo is not None:
        st.session_state['checkin_pending_photo'] = photo
        st.session_state['checkin_capture'] = ((membership_id, season_id, photo.file_id), str(uuid4()), current_time())
        st.rerun()
    st.stop()

page_header("Check in", compact=True)
if modern and rules.get('test_mode'):
    st.caption("Test season, open Wed 08:00 to Sun 18:00")

saved_result = st.session_state.pop("checkin_saved_result", None)
if saved_result is not None:
    with st.container(key="checkin_result"):
        points, location, owner_income, *saved_ids = saved_result
        territory_name, captured, unavailable = None, False, False
        saved = None
        if saved_ids:
            try:
                entries = db.list_drink_entries(season_id)
                saved = next((e for e in entries if e.id == saved_ids[0]), None)
                names = {t.id: t.name for t in get_territories()}
                if saved is not None and saved.territory_id:
                    territory_name = names.get(saved.territory_id)
                captured = captured_territory(saved_ids[0], entries) is not None
                if captured and territory_name is None:
                    territory_name = "the territory"
            except (APIError, RequestError, RuntimeError, ValueError):
                unavailable = True
        income = format_points(Decimal(owner_income) / 4) if owner_income else None
        # reward_card_html escapes every value, including the territory name.
        st.markdown(reward_card_html(format_points(points), location, territory=territory_name, captured=captured,
                                     team_mode=team_mode, owner_income=income, ownership_unavailable=unavailable),
                    unsafe_allow_html=True)
        if saved and saved.territory_boost_id and (saved.focus_multiplier or 1) <= TERRITORY_MULTIPLIER:
            st.caption(f"Territory boost ×{TERRITORY_MULTIPLIER:g} applied.")

if st.session_state.get('checkin_posted'):
    # The one button after a check-in. (The + tab in the bar starts the next one.)
    if st.button('Go to map', type='primary', width='stretch', key='checkin_go_map'):
        reset_camera()
        st.switch_page('pages/5_Map.py')
    st.stop()

if closed:
    opening = next_opening(now, season) if modern else None
    if opening:
        st.warning(f"Scoring is closed. Opens {opening:%a %d %b %Y at %H:%M:%S %Z} ({season.timezone_name}).")
    elif utc(now) < utc(season.starts_at):
        local_start = season.starts_at.astimezone(ZoneInfo(season.timezone_name))
        st.warning(f"This season starts {local_start:%d %b %Y at %H:%M:%S %Z} ({season.timezone_name}).")
    else:
        st.warning("This season has ended. Create or join a new lobby on the Lobbies page and make it current to play again.")
if waiting:
    st.warning(f"Next check-in in {waiting // 60}:{waiting % 60:02d}.")
    st.button("Refresh remaining wait")


capture = st.session_state.get('checkin_capture')
with st.container(key='checkin_photo'):
    # The photo fills all the space the controls leave free; Retake is a small round button on it.
    # Keep the preview inside the authenticated session, not a public media URL.
    encoded = b64encode(photo.getvalue()).decode('ascii')
    st.html(f'<img class="checkin-photo" src="data:image/jpeg;base64,{encoded}" alt="Your drink photo">')
    if st.button('Retake photo', icon=':material/photo_camera:', key='checkin_retake'):
        reset_camera()
        st.rerun()

size = None
amount = None
focus_multiplier = 1  # earned boosts are applied and checked by the server; the Focus screen no longer exists
time_multiplier = 1
if modern:
    try:
        time_info = db.time_status(player_id, season_id)
        if time_info.get('boost_ends_at'):
            time_multiplier = 1.25
            boost_end = datetime.fromisoformat(time_info['boost_ends_at']).astimezone(ZoneInfo(season.timezone_name))
            st.success(f'Time Duel ×1.25 until {boost_end:%H:%M}.')
    except (APIError, RequestError, RuntimeError, ValueError, PermissionError):
        pass  # The server applies any earned bonus on submission.
with st.container(key="drink_ui_panel_selection"):
    if modern:
        with st.container(key="drink_ui_drinks"):
            drink_type = st.radio("Drink", options=list(DRINK_LABELS), format_func=DRINK_LABELS.get,
                                  horizontal=True, width="stretch", label_visibility="collapsed")
        # A shot has no size, but its row keeps the same height (an invisible spacer in the same keyed
        # container, which has a minimum height, see drink_entries.css), so the photo above does not
        # jump when you switch.
        with st.container(key="drink_ui_sizes"):
            if drink_type == "shot":
                st.markdown('<span class="size-spacer" aria-hidden="true"></span>', unsafe_allow_html=True)
            else:
                size = st.radio("Size", options=list(SIZE_LABELS),
                                format_func=lambda value: size_label(drink_type, value, rules),
                                horizontal=True, width="stretch", label_visibility="collapsed")
        preview = base_points(drink_type, size, rules) * max(focus_multiplier, time_multiplier)
        point_word = "point" if preview == 1 else "points"
        with st.container(key="drink_ui_points"):
            st.info(f"**+{format_points(preview)} {point_word}**")
    else:
        st.caption("This season keeps its original scoring rules.")
        drink_type = st.selectbox("Drink type", options=["beer", "wine", "shot", "longdrink"])
        if drink_type in ("beer", "wine"):
            amount = st.number_input("Amount (units)", min_value=0.1, value=1.0, step=0.1)

territory_problem = None
with st.container(key="drink_ui_panel_location"):
    device_gps, accuracy_m, location_problem = current_location()
    location_messages = {
        "waiting": "Finding your location… Allow access if asked.",
        "off": "Location is off. Turn it on in Profile.",
        "stale": "Updating your location…",
        "denied": "Location is blocked in your browser. Allow it in the browser settings, then turn it on in Profile.",
        "unavailable": "Can't find your position. Move closer to a window or outside.",
        "timeout": "Still searching for your position…",
        "unsupported": "This browser can't share its location.",
        "invalid": "Couldn't read your location. Reload the page.",
    }
    if location_problem in ("off", "denied", "unsupported", "invalid"):
        st.warning(location_messages[location_problem])
        if location_problem in ("off", "denied") and st.button("Open Profile", key="location_open_profile"):
            st.session_state["profile_view"] = "menu"
            st.switch_page("pages/1_Profile.py")
    elif location_problem:
        st.caption(location_messages[location_problem])
    elif accuracy_m > MAX_GPS_ACCURACY_M:
        st.warning(f"Your location is only accurate to about {accuracy_m:.0f} m (need {MAX_GPS_ACCURACY_M:.0f} m). Step outside.")
    else:
        place = ""
        if modern and device_gps is not None:
            try:
                territories = get_territories()
                preview_result, preview_territory = evaluate_location(device_gps, accuracy_m, territories)
                if preview_result == "matched":
                    place = " in " + next(t.name for t in territories if t.id == preview_territory)
                elif preview_result == "outside":
                    place = ", outside the territories (season points only)"
                elif preview_result == "uncertain":
                    territory_problem = AMBIGUOUS_TERRITORY_MESSAGE
                    place = ", territory could not be assigned"
            except (APIError, RequestError, RuntimeError):
                pass  # The territory is checked again on submission.
        st.caption(f"Location found, accurate to {accuracy_m:.0f} m{place}")


# Recover a lost successful reply even after the scoring window closes.
recovered = next((item for item in recent_entries if capture and item.id == capture[1]), None)
if recovered is not None:
    finish_checkin(recovered)

blockers = [
    location_blocker(location_problem, accuracy_m),
    territory_problem,
    checkin_message("scoring_closed") if closed else None,
    f"Your next check-in is available in {waiting // 60}:{waiting % 60:02d}. Wait, then press Refresh remaining wait and submit again." if waiting else None,
    checkin_message("missing_photo") if photo is None or capture is None else None,
]
if action_button("Submit", type="primary", width="stretch", problems=blockers,
                 details="A blocked submission awards no points. Your photo and drink selection stay on this page while you fix the requirements. Location is checked again when you submit."):
    submitted_at = current_time() if modern else datetime.now().astimezone()
    _, capture_id, captured_at = capture

    try:
        recent_entries = db.list_drink_entries_for_membership(membership_id)
        entry = next((saved for saved in recent_entries if saved.id == capture_id), None)
        if entry is None:
            _photo_gps, clean_photo = prepare_checkin_photo(photo.getvalue())  # photo GPS is not used (R-L01)
            if modern:
                entry = create_scored_entry(membership_id, season, drink_type, size, f"{lobby_id}/{capture_id}.jpg",
                    device_gps, accuracy_m, submitted_at, get_territories(), recent_entries, entry_id=capture_id)
            else:
                entry = create_drink_entry(
                    membership_id,
                    season_id,
                    drink_type,
                    amount,
                    f"{lobby_id}/{capture_id}.jpg",
                    device_gps,
                    accuracy_m,
                    submitted_at,
                    get_territories(),
                    recent_entries,
                )
            entry = replace(entry, id=capture_id, photo_captured_at=captured_at)
            entry = db.save_drink_entry_photo(player_id, lobby_id, entry, clean_photo)
    except InvalidCheckinPhoto as error:
        explain(str(error))
    except CheckinRejected as rejected:
        explain(checkin_message(rejected.reason), details="This submission was rejected. Your photo and selections are kept so you can fix the problem and retry.")
    except PermissionError:
        explain("Your lobby access could not be confirmed. Open the Lobby page and select a lobby you belong to, then retry.")
    except (RuntimeError, APIError, RequestError, StorageException, OSError) as error:
        service_error(error, "We couldn't confirm the check-in was saved. Keep this photo and submit again to recover the saved result without awarding it twice.", popup=True)
    else:
        finish_checkin(entry)
