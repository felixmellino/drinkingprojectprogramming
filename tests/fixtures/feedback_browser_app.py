"""Real check-in page with synthetic inputs for manual error-feedback QA.

Run: streamlit run tests/fixtures/feedback_browser_app.py
No shared database, real photo, location permission or account is used.
"""
from dataclasses import replace
from io import BytesIO
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import streamlit as st
from PIL import Image
import camera_capture
import core.scoring_v1 as scoring
import data.db as db
import phone_location
import shared
from tests.test_checkins import INSIDE, TERRITORY
from tests.test_scoring_v1 import START, season
from theme import apply_theme

st.set_page_config(page_title="WeGoPub · Feedback QA")
apply_theme()
with st.sidebar:
    st.write("Local QA · Synthetic data")
    status = st.selectbox("Location state", ["off", "denied", "waiting", "stale", "timeout", "unsupported", "unavailable", "invalid", "inaccurate", "ready"])
    st.caption("Choose a location failure, then tap Submit. Dismiss the explanation and choose ready to retry with the same photo.")
    if st.button("Reset local check-in"):
        for key in list(st.session_state):
            if key.startswith("checkin_") or key == "qa_entries":
                del st.session_state[key]
        st.rerun()

game = season()
photo = BytesIO()
Image.new("RGB", (600, 450), "#799caf").save(photo, "JPEG")
photo.file_id = "synthetic-feedback-photo"
saved = st.session_state.setdefault("qa_entries", [])

db.get_client = lambda: (_ for _ in ()).throw(RuntimeError("Shared database disabled in feedback QA"))
db.list_drink_entries_for_membership = lambda _, **kwargs: list(saved)
db.list_drink_entries = lambda _: list(saved)
db.list_seasons_for_lobby = lambda _: [game]
db.time_status = lambda *_: {"boost_ends_at": None}


def save_local(_player, _lobby, entry, _photo):
    entry = replace(entry, event_order=len(saved) + 1)
    saved.append(entry)
    return entry


db.save_drink_entry_photo = save_local
shared.require_login = lambda: "local-player"
shared.require_active_membership = lambda: ("member", "lobby", "season")
shared.show_logged_in_as = lambda: None
shared.get_territories = lambda: [TERRITORY]
scoring.current_time = lambda: START
camera_capture.camera_photo = lambda **_: photo
phone_location.track_location = lambda: None
phone_location.current_location = lambda: ((INSIDE, 80 if status == "inaccurate" else 10, None)
                                         if status in {"ready", "inaccurate"} else (None, None, status))
st.session_state["current_lobby_mode"] = "individual"
st.navigation([st.Page(str(ROOT / "pages/3_Check_in.py"), title="Check in", default=True)], position="hidden").run()
