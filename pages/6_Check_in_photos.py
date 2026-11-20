"""Show check-in photos to the members of the lobby where they were taken."""

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
from drink_entry_ui import page_header, section_heading
from photo_history_ui import full_photo, history_pages, game_night_label, memory_tile, photo_metadata, photo_thumbnail
from shared import require_active_membership, require_login, show_logged_in_as


def entry_label(entry: dict) -> str:
    timestamp = entry["captured_at"] or entry["submitted_at"]
    time = show_time(timestamp, entry.get("timezone_name", "UTC"))
    return f"{entry['username']} · {time}"


def show_time(timestamp: str, zone_name: str) -> str:
    time = utc(datetime.fromisoformat(timestamp)).astimezone(ZoneInfo(zone_name))
    return f"{time:%d %b %Y at %H:%M:%S %Z (%z)} · {zone_name}"


STEP = 24  # photos shown at first and added by each "Load more"


def load_more(count):
    st.session_state['history_shown'] = count + STEP


def open_photo(entry_id):
    st.session_state['history_detail_id'] = entry_id


def close_photo():
    st.session_state.pop('history_detail_id', None)


player_id = require_login()
show_logged_in_as()
_, lobby_id, _ = require_active_membership()

page_header("Photos")
if st.session_state.pop("photo_deleted", False):
    st.success("Photo deleted. Your score is unchanged.")
if st.session_state.pop("checkin_corrected", False):
    st.success("Correction saved. Ownership and all affected owner income have been recalculated.")

try:
    entries = db.list_checkin_photos(player_id, lobby_id)
    if not entries:
        st.info("No photo history is available to you in this lobby yet. Other players' photos depend on their privacy settings.")
        st.stop()

except PermissionError:
    st.error("Choose a lobby you belong to to view its photos.")
    st.stop()
except (APIError, RequestError, RuntimeError, StorageException):
    st.error("We couldn't load the photo. Try again.")
    st.stop()

entries_by_id = {item["id"]: item for item in entries}
detail_id = st.session_state.get("history_detail_id")
if detail_id not in entries_by_id:
    st.session_state.pop("history_detail_id", None)
    detail_id = None

FOOTER = (f"Photos stay until {PHOTO_RETENTION_DAYS} days after their season ends. Deleting your photo keeps your score. "
          "Sharing: Profile → Account & security → Photo privacy.")


if len(entries) > 1 and detail_id is None:
    # Tabs like a phone gallery: everything shared with you, or only your own.
    with st.container(key="photo_tabs"):
        show = st.radio("Show", ["All", "Mine"], horizontal=True, key="photo_filter", label_visibility="collapsed")
    shown = [item for item in entries if show == "All" or item["is_owner"]]
    if not shown:
        st.info("You have no check-in photos in this lobby yet.")
        st.stop()
    if st.session_state.get("history_filter") != show:   # a new filter starts at the newest photos again
        st.session_state["history_filter"] = show
        st.session_state["history_shown"] = STEP
    count = min(len(shown), max(STEP, st.session_state.get("history_shown", STEP)))
    # One continuous list, newest first, grouped by game night.
    visible_nights = history_pages(shown[:count], max_photos=count + 1, max_nights=count + 1)[0]

    visible = [item for _, _, items in visible_nights for item in items]
    ids = [item['id'] for item in visible]
    photos = {}
    try:
        # The list can hold more photos than one authorization batch allows: every slice of at most
        # MAX_PHOTO_BATCH photos gets its own fresh audience snapshot, never a cached listing.
        for start in range(0, len(ids), db.MAX_PHOTO_BATCH):
            batch = ids[start:start + db.MAX_PHOTO_BATCH]
            try:
                originals = db.download_checkin_photos(player_id, lobby_id, batch)
                # Decode one thumbnail at a time and drop the originals, to bound memory for large camera images.
                photos.update({entry_id: photo_thumbnail(originals.get(entry_id)) for entry_id in batch})
            except (APIError, RequestError, RuntimeError, StorageException):
                photos.update(dict.fromkeys(batch))   # this slice failed; the others still show
    except PermissionError:
        st.warning("Photo access changed. Refresh to load the current photo history.")
        st.stop()
    if any(photos.get(item['id']) is None and item.get('has_photo',True) for item in visible):
        st.warning('Some photos could not be loaded. Their details are still available.')

    for start, end, night_entries in visible_nights:
        label = f"{len(night_entries)} check-in{'s' if len(night_entries) != 1 else ''}"
        st.markdown(f'<div class="memory-night-label"><strong>{game_night_label(start, end)}</strong>'
                    f'<span>{label}</span></div>', unsafe_allow_html=True)
        with st.container(key=f"memory_grid_{start.date().isoformat()}"):
            for item in night_entries:
                with st.container(key=f"memory_tile_{item['id']}"):
                    photo = photos[item['id']]
                    memory_tile(item, photo, key=f"memory_tile_{item['id']}", on_open=open_photo)

    if count < len(shown):
        st.button("Load more", key="photo_more", on_click=load_more, args=(count,), width="stretch")
        st.caption(f"{count} of {len(shown)} photos")
    st.caption(FOOTER)
    st.stop()

if len(entries) > 1:
    st.button("Back to photos", key="photo_back", type="tertiary", icon=":material/arrow_back:", on_click=close_photo)
entry = entries_by_id[detail_id] if detail_id in entries_by_id else entries_by_id[next(iter(entries_by_id))]

try:
    photo = db.download_checkin_photo(player_id, lobby_id, entry["id"])
except PermissionError:
    st.warning("Photo access changed. Refresh to load the current photo history.")
    st.stop()
except (APIError, RequestError, RuntimeError, StorageException):
    st.error("We couldn't load the photo. Try again.")
    photo = None

# The opened photo fills almost the whole screen; details follow below it.
location = "Outside game territories" if entry["location"] == "outside" else entry["territory"]
full_photo(entry, photo, location or "No territory assigned")
if photo is None:
    st.caption("This check-in's photo is unavailable. Removing a photo keeps the check-in and its score.")
time_label = "Photo received" if entry["captured_at"] else "Check-in submitted"
st.text(f"{time_label} · {entry_label(entry)}")

# Scores and revision history remain visible after photo deletion.
if entry.get("rule_version") == "v1":
    model, season = entry["entry"], entry["season"]
    zone = season.timezone_name
    with st.container(key="drink_ui_panel_details"):
        section_heading("02", "Points & details", "The current award for this check-in.")
        selection = DRINK_LABELS.get(model.drink_type, model.drink_type)
        if model.size:
            selection += f" · {size_label(model.drink_type, model.size, season.scoring_rules)}"
        st.text(selection)
        territory_points = model.points_awarded if model.location_check_result == "matched" else 0
        st.text(f"Drinker: +{format_points(model.points_awarded + model.time_bonus)} season points · +{format_points(territory_points)} territory points")
        if model.focus_attempt_id:
            st.caption('Focus boost ×1.5 · This check-in keeps its earned multiplier after the boost ends.')
        if model.owner_bonus_quarters:
            income = format_points(Decimal(model.owner_bonus_quarters) / 4)
            st.text(f"Additional owner income: +{income} season points to {entry['income_recipient']}")
        else:
            st.text("No owner income for this check-in.")
        st.caption("Awards reflect the current corrected history. Corrections elsewhere can change the owner-income recipient.")
    with st.expander("Exact timestamps"):
        st.text(f"Submitted · {show_time(entry['submitted_at'], zone)}")
        if entry["captured_at"]:
            st.text(f"Photo received · {show_time(entry['captured_at'], zone)}")
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
            with st.container(key="drink_ui_drinks"):
                chosen_drink = st.radio("Correct drink", list(DRINK_LABELS),
                    index=list(DRINK_LABELS).index(model.drink_type), format_func=DRINK_LABELS.get,
                    horizontal=True, width="stretch", key=f"{key}_drink")
            chosen_size = None
            if chosen_drink != "shot":
                with st.container(key="drink_ui_sizes"):
                    chosen_size = st.radio("Correct size", list(SIZE_LABELS),
                        index=list(SIZE_LABELS).index(model.size) if model.size in SIZE_LABELS else 0,
                        format_func=lambda value: size_label(chosen_drink, value, season.scoring_rules),
                        horizontal=True, width="stretch", key=f"{key}_size")
            st.info(f"Corrected base award: {base_points(chosen_drink, chosen_size, season.scoring_rules)} points")
            unchanged = chosen_drink == model.drink_type and chosen_size == model.size
            if st.button("Save correction", key=f"{key}_save", type="primary", width="stretch", disabled=unchanged):
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

else:
    with st.container(key="drink_ui_panel_details"):
        section_heading("02", "Drink & points", "Original details for this historical check-in.")
        photo_metadata(entry)

# Keep deletion available even when the download failed, so partial deletions
# can still be retried. This action never changes the scored entry.
if entry["is_owner"] and entry["has_photo"]:
    with st.expander("Manage your photo"):
        st.caption("Permanently remove the image. Your check-in, points and owner income stay.")
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
