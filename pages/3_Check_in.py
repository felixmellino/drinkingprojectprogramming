"""Log a drink with a required camera photo and a location check."""

from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError
from storage3.utils import StorageException

import data.db as db
from core.checkin_photo import InvalidCheckinPhoto, prepare_checkin_photo
from core.checkins import CheckinRejected, create_drink_entry
from shared import require_active_membership, require_login, show_logged_in_as

player_id = require_login()
show_logged_in_as()
membership_id, lobby_id, season_id = require_active_membership()

st.title("Check in")

saved_result = st.session_state.pop("checkin_saved_result", None)
if saved_result is not None:
    points, location = saved_result
    if points == 0:
        st.warning("Saved in your history with zero points.")
    elif location == "outside":
        st.success(f"Logged! +{points} season points. Your location is outside the game territories.")
    else:
        st.success(f"Logged! +{points} points.")

drink_type = st.selectbox("Drink type", options=["beer", "wine", "shot", "longdrink"])
amount = None
if drink_type in ("beer", "wine"):
    amount = st.number_input("Amount (units)", min_value=0.1, value=1.0, step=0.1)

photo_number = st.session_state.get("checkin_photo_number", 0)
photo = st.camera_input("Take a fresh photo of your drink", key=f"checkin_photo_{photo_number}")
capture = st.session_state.get("checkin_capture")
if photo is not None:
    capture_key = (membership_id, season_id, photo.file_id)
    if capture is None or capture[0] != capture_key:
        capture = (capture_key, str(uuid4()), datetime.now(timezone.utc))
        st.session_state["checkin_capture"] = capture
else:
    st.session_state.pop("checkin_capture", None)

st.caption("TODO: real GPS capture. Enter your current coordinates manually for now.")
device_lat = st.number_input(
    "Latitude", min_value=-90.0, max_value=90.0, value=None, format="%.6f", key=f"checkin_lat_{photo_number}"
)
device_lng = st.number_input(
    "Longitude", min_value=-180.0, max_value=180.0, value=None, format="%.6f", key=f"checkin_lng_{photo_number}"
)


if st.button("Submit", disabled=photo is None) and photo is not None and capture is not None:
    submitted_at = datetime.now().astimezone()
    _, capture_id, captured_at = capture
    device_gps = None
    if device_lat is not None and device_lng is not None:
        device_gps = (device_lat, device_lng)

    try:
        recent_entries = db.list_drink_entries_for_membership(membership_id)
        entry = next((saved for saved in recent_entries if saved.id == capture_id), None)
        if entry is None:
            photo_gps, clean_photo = prepare_checkin_photo(photo.getvalue())
            entry = create_drink_entry(
                membership_id,
                season_id,
                drink_type,
                amount,
                f"{lobby_id}/{capture_id}.jpg",
                device_gps,
                photo_gps,
                submitted_at,
                db.list_territories(),
                recent_entries,
            )
            entry = replace(entry, id=capture_id, photo_captured_at=captured_at)
            entry = db.save_drink_entry_photo(player_id, lobby_id, entry, clean_photo)
    except InvalidCheckinPhoto as error:
        st.error(str(error))
    except CheckinRejected as rejected:
        messages = {
            "missing_photo": "A photo is required.",
            "unknown_drink_type": "Unrecognized drink type.",
            "missing_amount": "Enter an amount for this drink.",
            "duplicate_check_in": "You already logged this drink a moment ago.",
            "location_unavailable": "Enter your latitude and longitude, then try again.",
            "location_uncertain": "We couldn't verify your location. Check your coordinates and try again.",
        }
        st.error(messages.get(rejected.reason, rejected.reason))
    except PermissionError:
        st.error("Choose a lobby you belong to before checking in.")
    except (APIError, RequestError, RuntimeError, StorageException):
        st.error("We couldn't confirm the check-in was saved. Try submitting again.")
    else:
        st.session_state["checkin_saved_result"] = (entry.points_awarded, entry.location_check_result)
        st.session_state["checkin_photo_number"] = photo_number + 1
        st.rerun()
