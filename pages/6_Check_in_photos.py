"""Show check-in photos to the members of the lobby where they were taken."""

from base64 import b64encode
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError
from storage3.utils import StorageException

import data.db as db
from core.constants import PHOTO_RETENTION_DAYS
from core.checkins import CheckinRejected
from core.scoring_v1 import (DRINK_LABELS, SIZE_LABELS, base_points, can_correct, current_time, format_points, size_label, utc)
from shared import require_active_membership, require_login, show_logged_in_as


def entry_label(entry: dict) -> str:
    timestamp = entry["captured_at"] or entry["submitted_at"]
    time = show_time(timestamp, entry.get("timezone_name", "UTC"))
    return f"{entry['username']} · {time}"


def show_time(timestamp: str, zone_name: str) -> str:
    time = utc(datetime.fromisoformat(timestamp)).astimezone(ZoneInfo(zone_name))
    return f"{time:%d %b %Y at %H:%M:%S %Z (%z)} · {zone_name}"


player_id = require_login()
show_logged_in_as()
_, lobby_id, _ = require_active_membership()

st.title("Lobby photos")
st.caption(f"Photos are available until {PHOTO_RETENTION_DAYS} days after their season ends. Deleting your photo keeps your score.")
if st.session_state.pop("photo_deleted", False):
    st.success("Photo deleted. Your score is unchanged.")
if st.session_state.pop("checkin_corrected", False):
    st.success("Correction saved. Ownership and all affected owner income have been recalculated.")

try:
    entries = db.list_checkin_photos(player_id, lobby_id)
    if not entries:
        st.info("Your lobby has no check-in photos available.")
        st.stop()

    entries_by_id = {item["id"]: item for item in entries}
    selected_id = st.selectbox("Check-in", list(entries_by_id), format_func=lambda value: entry_label(entries_by_id[value]))
    if selected_id is None:
        st.stop()
    entry = entries_by_id[selected_id]
except PermissionError:
    st.error("Choose a lobby you belong to to view its photos.")
    st.stop()
except (APIError, RequestError, RuntimeError, StorageException):
    st.error("We couldn't load the photo. Try again.")
    st.stop()

# Keep deletion available if a previous attempt removed the file but its
# database update failed. Loading a missing file must not block that retry.
if entry["is_owner"] and entry["has_photo"]:
    confirmed = st.checkbox("Permanently delete this photo", key=f"confirm_delete_{entry['id']}")
    if st.button("Delete my photo", disabled=not confirmed):
        try:
            db.delete_checkin_photo(player_id, lobby_id, entry["id"])
        except PermissionError:
            st.error("Only the photo's owner can delete it.")
        except (APIError, RequestError, RuntimeError, StorageException):
            st.error("We couldn't finish deleting the photo. Try again.")
        else:
            st.session_state["photo_deleted"] = True
            st.rerun()

try:
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

    time_label = "Photo received" if entry["captured_at"] else "Check-in submitted"
    st.text(f"{time_label} · {entry_label(entry)}")
    location = "Outside game territories" if entry["location"] == "outside" else entry["territory"]
    if location:
        st.text(location)

# Scores and revision history remain visible after photo deletion.
if entry.get("rule_version") == "v1":
    model, season = entry["entry"], entry["season"]
    zone = season.timezone_name
    st.text(f"Submitted · {show_time(entry['submitted_at'], zone)}")
    if entry["captured_at"]:
        st.text(f"Photo received · {show_time(entry['captured_at'], zone)}")
    selection = DRINK_LABELS.get(model.drink_type, model.drink_type)
    if model.size:
        selection += f" · {size_label(model.drink_type, model.size, season.scoring_rules)}"
    st.text(selection)
    territory_points = model.points_awarded if model.location_check_result == "matched" else 0
    st.text(f"Drinker: +{model.points_awarded} season points · +{territory_points} territory points")
    if model.owner_bonus_quarters:
        income = format_points(Decimal(model.owner_bonus_quarters) / 4)
        st.text(f"Additional owner income: +{income} season points to {entry['income_recipient']}")
    else:
        st.text("No owner income for this check-in.")
    st.caption("Awards reflect the current corrected history. Corrections elsewhere can change the owner-income recipient.")
    if model.revision:
        st.text(f"Corrected · {show_time(entry['corrected_at'], zone)} · revision {model.revision}")
        try:
            revisions = db.list_checkin_revisions(player_id, lobby_id, model.id)
        except (APIError, RequestError, RuntimeError, PermissionError):
            st.warning("The correction history could not be loaded. Refresh to try again.")
        else:
            with st.expander("Correction history"):
                st.table([{"Revision": r["revision"],
                    "Before": f"{r['old_drink_type']} / {r['old_size'] or 'one serving'}",
                    "After": f"{r['new_drink_type']} / {r['new_size'] or 'one serving'}",
                    "Changed": show_time(r["corrected_at"], zone)} for r in revisions])
    if entry["is_owner"] and can_correct(model, season, current_time()):
        with st.expander("Correct drink or size"):
            st.caption("Available for two minutes after the original submission, before season end. A correction can change later owner income and territory ownership.")
            key = f"correct_{model.id}_{model.revision}"
            chosen_drink = st.radio("Correct drink", list(DRINK_LABELS),
                index=list(DRINK_LABELS).index(model.drink_type), format_func=DRINK_LABELS.get,
                horizontal=True, key=f"{key}_drink")
            chosen_size = None
            if chosen_drink != "shot":
                chosen_size = st.radio("Correct size", list(SIZE_LABELS),
                    index=list(SIZE_LABELS).index(model.size) if model.size in SIZE_LABELS else 0,
                    format_func=lambda value: size_label(chosen_drink, value, season.scoring_rules), horizontal=True, key=f"{key}_size")
            st.info(f"Corrected base award: {base_points(chosen_drink, chosen_size, season.scoring_rules)} points")
            unchanged = chosen_drink == model.drink_type and chosen_size == model.size
            if st.button("Save correction", key=f"{key}_save", disabled=unchanged):
                try:
                    db.correct_checkin(player_id, lobby_id, model.id, chosen_drink, chosen_size, model.revision)
                except PermissionError:
                    st.error("Only the submitter can correct this entry.")
                except CheckinRejected as error:
                    if error.reason == "correction_conflict":
                        st.error("This entry changed in another session. Refresh and review it before retrying.")
                    else:
                        st.error("The correction window has closed or this selection is invalid. Refresh to see the saved result.")
                except (APIError, RequestError, RuntimeError):
                    st.error("The correction result is uncertain. Refresh and check the saved entry before retrying.")
                else:
                    st.session_state["checkin_corrected"] = True
                    st.rerun()
