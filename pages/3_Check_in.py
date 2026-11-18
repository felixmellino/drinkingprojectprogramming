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
from camera_capture import CameraCancelled, camera_photo
from core.checkin_photo import InvalidCheckinPhoto, prepare_checkin_photo
from core.checkins import CheckinRejected, create_drink_entry
from core.checkin_feedback import captured_territory
from core.scoring_v1 import (DRINK_LABELS, SIZE_LABELS, base_points, cooldown_remaining,
    create_scored_entry, current_time, format_points, next_opening, replay_season, rules_for, scoring_open, size_label, utc)
from core.constants import MAX_GPS_ACCURACY_M
from core.location import evaluate_location
from drink_entry_ui import context_line, page_header, section_heading
from phone_location import current_location, track_location
from shared import get_territories, require_active_membership, require_login, show_logged_in_as

player_id = require_login()
show_logged_in_as()
membership_id, lobby_id, season_id = require_active_membership()

seasons = db.list_seasons_for_lobby(lobby_id)
season = next((item for item in seasons if item.id == season_id), None)
if season is None:
    st.info("Choose a season on the Lobby page first.")
    st.stop()
modern = season.scoring_version == "v1"
rules = rules_for(season) if modern else None
now = current_time()
recent_entries = db.list_drink_entries_for_membership(membership_id)
track_location()


def reset_camera():
    """Forget an unsaved capture; a new component key opens a fresh stream."""
    for key in ('checkin_pending_photo', 'checkin_capture', 'checkin_posted', 'checkin_saved_result'):
        st.session_state.pop(key, None)
    st.session_state['checkin_photo_number'] = st.session_state.get('checkin_photo_number', -1) + 1


def finish_checkin(entry):
    reset_camera()
    st.session_state['checkin_posted'] = True
    st.session_state['checkin_saved_result'] = (entry.points_awarded, entry.location_check_result,
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
if photo is None and not st.session_state.get('checkin_posted'):
    # Only the camera occupies the viewport. GPS continues in its hidden component.
    st.markdown("""<style>
      .st-key-checkin_camera_stage {position:fixed!important;inset:0;z-index:100000;
        width:100vw!important;max-width:none!important;background:#080d0b;overflow:hidden;}
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

page_header("Check in", "Take a photo. Choose your drink. Post.", compact=True)
if modern:
    lobby_time = now.astimezone(ZoneInfo(season.timezone_name))
    context_line(st.session_state.get("current_lobby_name", "Your lobby"),
                 f"{lobby_time:%a %d %b · %H:%M %Z} · {season.timezone_name}")
    if rules.get('test_mode'):
        st.info('TEST SEASON · Posting is open Wednesday 08:00–Sunday 18:00 in the lobby timezone.')

saved_result = st.session_state.pop("checkin_saved_result", None)
if saved_result is not None:
    points, location, owner_income, *saved_ids = saved_result
    if points == 0:
        st.warning("Saved in your history with zero points.")
    elif location == "outside":
        st.success(f"Logged! +{points} season points. Your location is outside the game territories.")
    else:
        st.success(f"Logged! +{points} points.")
    if owner_income:
        st.info(f"The territory's previous owner also earned {format_points(Decimal(owner_income) / 4)} season points. You kept all your points.")
    if saved_ids:
        try:
            territory_id = captured_territory(saved_ids[0], db.list_drink_entries(season_id))
            if territory_id:
                territory_name = next((t.name for t in get_territories() if t.id == territory_id), "the territory")
                # Plain text prevents a territory label from injecting Markdown.
                st.success("Territory captured!")
                st.text(f"You captured {territory_name}!")
                st.caption("Ownership change caused by this check-in. The Map shows the latest standings.")
        except (APIError, RequestError, RuntimeError, ValueError):
            st.caption("Your check-in was saved. The ownership update is unavailable; check the Map or Leaderboard.")

if st.session_state.get('checkin_posted'):
    st.info('Your drink is posted. Find it in Photo history or check the Leaderboard.')
    if st.button('New check-in', type='primary', width='stretch'):
        reset_camera()
        st.rerun()
    st.stop()

period_closed = not utc(season.starts_at) <= utc(now) < utc(season.ends_at)
closed = period_closed or (modern and not scoring_open(now, season))
waiting = cooldown_remaining(membership_id, now, recent_entries, rules["cooldown_seconds"]) if modern else 0
if closed:
    opening = next_opening(now, season) if modern else None
    if opening:
        st.warning(f"Scoring is closed. Opens {opening:%a %d %b %Y at %H:%M:%S %Z} ({season.timezone_name}).")
    elif utc(now) < utc(season.starts_at):
        st.warning(f"This season starts {season.starts_at:%d %b %Y at %H:%M:%S %Z}.")
    else:
        st.warning("This season has ended. Start or choose a new season on the Lobby page.")
if waiting:
    st.warning(f"Wait {waiting // 60}:{waiting % 60:02d} before your next check-in. Your photo and selections stay here.")
    st.button("Refresh remaining wait")


capture = st.session_state.get('checkin_capture')
with st.container(key='drink_ui_panel_camera'):
    section_heading('01', 'Your photo', 'Looking good? Choose your drink below.')
    # Keep the preview inside the authenticated session, not a public media URL.
    encoded = b64encode(photo.getvalue()).decode('ascii')
    st.html(f'<img src="data:image/jpeg;base64,{encoded}" alt="Your drink photo" '
            'style="display:block;width:100%;max-height:320px;object-fit:contain;border-radius:22px;background:#edf2e9">')
    if st.button('Retake photo', icon=':material/photo_camera:', width='stretch'):
        reset_camera()
        st.rerun()
    st.caption('Shared only with your lobby, alongside your username, photo receipt time and territory.')

size = None
amount = None
with st.container(key="drink_ui_panel_selection"):
    section_heading("02", "Choose your drink", "One drink, one size. Your points update as you choose.")
    if modern:
        with st.container(key="drink_ui_drinks"):
            drink_type = st.radio("Drink", options=list(DRINK_LABELS), format_func=DRINK_LABELS.get,
                                  horizontal=True, width="stretch")
        if drink_type != "shot":
            with st.container(key="drink_ui_sizes"):
                size = st.radio("Size", options=list(SIZE_LABELS),
                                format_func=lambda value: size_label(drink_type, value, rules),
                                horizontal=True, width="stretch")
        else:
            st.caption("One shot serving. No size selection needed.")
        preview = base_points(drink_type, size, rules)
        point_word = "point" if preview == 1 else "points"
        with st.container(key="drink_ui_points"):
            st.info(f"**+{preview} season {point_word}**  \n+{preview} territory {point_word} if your location matches a territory.")
        st.caption("Another territory owner's 25% season income is additional; your points stay the same.")
    else:
        st.caption("This existing season keeps its original scoring rules. New seasons use the new scoring system.")
        drink_type = st.selectbox("Drink type", options=["beer", "wine", "shot", "longdrink"])
        if drink_type in ("beer", "wine"):
            amount = st.number_input("Amount (units)", min_value=0.1, value=1.0, step=0.1)

with st.container(key="drink_ui_panel_location"):
    section_heading("03", "Location", "Your location assigns this drink to a territory.")
    device_gps, accuracy_m, location_problem = current_location()
    location_messages = {
        "waiting": "Finding your location… Allow location access if your browser asks.",
        "stale": "Your last location is more than a minute old. Finding a new one…",
        "denied": "Location access is blocked. Allow location for this site in your browser settings, then reload the page.",
        "unavailable": "Your phone can't find its position right now. Move closer to a window or outside.",
        "timeout": "Finding your position is taking long. Keep the page open, it keeps trying.",
        "unsupported": "This browser can't share its location. Try another browser on your phone.",
        "invalid": "Something went wrong reading your location. Reload the page.",
    }
    if location_problem in ("denied", "unsupported", "invalid"):
        st.warning(location_messages[location_problem])
    elif location_problem:
        st.caption(location_messages[location_problem])
    elif accuracy_m > MAX_GPS_ACCURACY_M:
        st.warning(
            f"Your location is only accurate to about {accuracy_m:.0f} m (we need {MAX_GPS_ACCURACY_M:.0f} m or better). "
            "Step outside or wait a moment; it updates by itself."
        )
    else:
        st.caption(f"Location found automatically, accurate to about {accuracy_m:.0f} m.")
    if modern and device_gps is not None and accuracy_m <= MAX_GPS_ACCURACY_M:
        try:
            territories = get_territories()
            preview_result, preview_territory = evaluate_location(device_gps, accuracy_m, territories)
            if preview_result == "matched":
                name = next(t.name for t in territories if t.id == preview_territory)
                owner = replay_season(db.list_drink_entries(season_id)).owners.get(preview_territory)
                context_line("Detected territory", name)
                if owner == membership_id:
                    st.text("You currently own this territory. Your check-in earns normal base points.")
                elif owner:
                    owner_name = db.membership_display_name(owner, lobby_id)
                    income = format_points(Decimal(preview) / 4)
                    st.text(f"Current owner: {owner_name} · estimated additional owner income: {income} season points")
                else:
                    st.text("Currently unclaimed. No owner income on its first accepted check-in.")
            elif preview_result == "outside":
                st.info(f"Outside game territories: +{preview} season points, no territory points or owner income.")
            st.caption("Preview only. Location evidence, ownership and eligibility are checked again on submission.")
        except (APIError, RequestError, RuntimeError):
            st.warning("The territory preview is unavailable. It will be checked again on submission.")


# Recover a lost successful reply even after the scoring window closes.
recovered = next((item for item in recent_entries if capture and item.id == capture[1]), None)
if recovered is not None:
    finish_checkin(recovered)

if st.button("Submit", type="primary", width="stretch", disabled=photo is None or device_gps is None or closed or bool(waiting)) and photo is not None and capture is not None:
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
        st.error(str(error))
    except CheckinRejected as rejected:
        messages = {
            "scoring_closed": "Scoring has closed. Refresh to see the next opening.",
            "cooldown": "Wait two minutes between check-ins. Your photo and selections are kept; refresh the remaining wait.",
            "invalid_selection": "Choose a supported drink and size.",
            "invalid_photo": "Take a fresh camera photo and try again.",
            "invalid_territory": "We could not confirm the territory. Refresh and try again.",
            "missing_photo": "A photo is required.",
            "unknown_drink_type": "Unrecognized drink type.",
            "missing_amount": "Enter an amount for this drink.",
            "duplicate_check_in": "You already logged this drink a moment ago.",
            "location_unavailable": "We need your location. Wait until it's found, then submit again.",
            "location_uncertain": "Your location isn't accurate enough yet. Wait a moment, then submit again.",
        }
        st.error(messages.get(rejected.reason, rejected.reason))
    except PermissionError:
        st.error("Choose a lobby you belong to before checking in.")
    except RuntimeError as error:
        if str(error).startswith("Scoring setup is required"):
            st.error(str(error))
        else:
            st.error("We couldn't confirm the check-in was saved. Try submitting again.")
    except (APIError, RequestError, StorageException):
        st.error("We couldn't confirm the check-in was saved. Try submitting again.")
    else:
        finish_checkin(entry)
