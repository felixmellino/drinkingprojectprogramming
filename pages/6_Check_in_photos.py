"""Show check-in photos to the members of the lobby where they were taken."""

from base64 import b64encode
from datetime import datetime, timezone

import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError
from storage3.utils import StorageException

import data.db as db
from shared import require_active_membership, require_login, show_logged_in_as


def entry_label(entry: dict) -> str:
    timestamp = entry["captured_at"] or entry["submitted_at"]
    time = datetime.fromisoformat(timestamp).astimezone(timezone.utc).strftime("%d %b %Y at %H:%M:%S UTC")
    return f"{entry['username']} · {time}"


player_id = require_login()
show_logged_in_as()
_, lobby_id, _ = require_active_membership()

st.title("Lobby photos")

try:
    entries = db.list_checkin_photos(player_id, lobby_id)
    if not entries:
        st.info("Your lobby has no check-in photos yet.")
        st.stop()

    entry = st.selectbox("Check-in", entries, format_func=entry_label)
    if entry is None:
        st.stop()
    photo = db.download_checkin_photo(player_id, lobby_id, entry["id"])
except PermissionError:
    st.error("Choose a lobby you belong to to view its photos.")
    st.stop()
except (APIError, RequestError, RuntimeError, StorageException):
    st.error("We couldn't load the photo. Try again.")
    st.stop()

if photo is None:
    st.info("This check-in's photo is unavailable.")
else:
    # Inline the bytes after authorization so Streamlit does not create a media URL.
    encoded = b64encode(photo).decode("ascii")
    st.html(f'<img src="data:image/jpeg;base64,{encoded}" alt="Drink check-in photo" style="max-width:100%;height:auto">')

    time_label = "Photo captured" if entry["captured_at"] else "Check-in submitted"
    st.text(f"{time_label} · {entry_label(entry)}")
    location = "Outside game territories" if entry["location"] == "outside" else entry["territory"]
    if location:
        st.text(location)
