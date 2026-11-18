"""Private account menu; each option opens a focused view."""
import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError
import data.db as db
from profile_ui import show_profile
from shared import require_login

player_id = require_login()
try:
    show_profile(db.get_player(player_id))
except (APIError, RequestError, RuntimeError, OSError):
    st.error("Profile is unavailable. Please try again later.")
