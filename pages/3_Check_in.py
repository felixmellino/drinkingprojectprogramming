"""Log a drink: type/size, a required photo, and GPS.

Photo storage and real browser geolocation are not wired up yet -- see the
two TODOs below. Both are workarounds the team should replace:
  - GPS: Streamlit has no native geolocation, so this page takes a manual
    lat/lng entry for now instead of reading the device's real GPS.
  - Photo storage: the photo's bytes aren't uploaded anywhere yet; only a
    placeholder reference is stored. Wire up Supabase Storage before relying
    on Memories or re-checking a submitted photo.
"""

from datetime import datetime

import streamlit as st

import data.db as db
from core.checkins import CheckinRejected, create_drink_entry
from shared import get_territories, require_active_membership, require_login, show_logged_in_as

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

st.caption("TODO: real GPS capture. Enter your current coordinates manually for now.")
device_lat = st.number_input(
    "Latitude", min_value=-90.0, max_value=90.0, value=None, format="%.6f", key=f"checkin_lat_{photo_number}"
)
device_lng = st.number_input(
    "Longitude", min_value=-180.0, max_value=180.0, value=None, format="%.6f", key=f"checkin_lng_{photo_number}"
)


if st.button("Submit", disabled=photo is None):
    submitted_at = datetime.now().astimezone()
    device_gps = None
    if device_lat is not None and device_lng is not None:
        device_gps = (device_lat, device_lng)
    # TODO: upload photo.getvalue() to Supabase Storage and store the real
    # URL/path here instead of this placeholder.
    photo_ref = f"placeholder-{submitted_at.isoformat()}"

    recent_entries = db.list_drink_entries_for_membership(membership_id)
    territories = get_territories()

    try:
        entry = create_drink_entry(
            membership_id,
            season_id,
            drink_type,
            amount,
            photo_ref,
            device_gps,
            None,  # accuracy: manual entry reports none; real phone GPS will (R-L02)
            submitted_at,
            territories,
            recent_entries,
        )
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
    else:
        db.insert_drink_entry(entry)
        st.session_state["checkin_saved_result"] = (entry.points_awarded, entry.location_check_result)
        st.session_state["checkin_photo_number"] = photo_number + 1
        st.rerun()
