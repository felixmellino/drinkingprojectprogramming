"""Log a drink: type/size, a required photo, and the phone's GPS.

The location comes from the "Use my location" button (phone_location.py),
which asks the browser for the phone's GPS and its accuracy (R-L01, R-L02).

Photo storage is not wired up yet: the photo's bytes aren't uploaded
anywhere; only a placeholder reference is stored. Wire up Supabase Storage
before relying on Memories or re-checking a submitted photo.
"""

from datetime import datetime

import streamlit as st

import data.db as db
from core.checkins import CheckinRejected, create_drink_entry
from core.constants import MAX_GPS_ACCURACY_M
from core.location import parse_phone_reading
from phone_location import phone_location_button
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

st.write("Your location")
device_gps, accuracy_m, location_problem = parse_phone_reading(
    phone_location_button(key=f"checkin_location_{photo_number}")
)
location_messages = {
    "not_requested": "Tap the button so we can check which territory you're in.",
    "denied": "Location access is blocked. Allow location for this site in your browser settings, then tap the button again.",
    "unavailable": "Your phone couldn't find its position. Move closer to a window or outside and tap the button again.",
    "timeout": "Finding your position took too long. Tap the button again.",
    "unsupported": "This browser can't share its location. Try another browser on your phone.",
    "invalid": "Something went wrong reading your location. Tap the button again.",
}
if location_problem:
    st.caption(location_messages[location_problem])
elif accuracy_m > MAX_GPS_ACCURACY_M:
    st.warning(
        f"Your location is only accurate to about {accuracy_m:.0f} m (we need {MAX_GPS_ACCURACY_M:.0f} m or better). "
        "Step outside or wait a moment, then tap the button again."
    )
else:
    st.caption(f"Location found, accurate to about {accuracy_m:.0f} m.")


if st.button("Submit", disabled=photo is None or device_gps is None):
    submitted_at = datetime.now().astimezone()
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
            accuracy_m,
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
            "location_unavailable": "We need your location. Tap “Use my location”, then submit again.",
            "location_uncertain": "Your location isn't accurate enough yet. Tap “Update my location”, then submit again.",
        }
        st.error(messages.get(rejected.reason, rejected.reason))
    else:
        db.insert_drink_entry(entry)
        st.session_state["checkin_saved_result"] = (entry.points_awarded, entry.location_check_result)
        st.session_state["checkin_photo_number"] = photo_number + 1
        st.rerun()
