"""WeGoPub entry point -- nav shell only, no rules, no DB calls.

Actual login/account creation lives in account_ui.py, to keep this
file small and avoid everyone colliding on it as the team adds pages.
"""

import streamlit as st

from shared import require_login

st.set_page_config(page_title="WeGoPub", page_icon="🍺")
st.title("🍺 WeGoPub")

require_login()
st.success(f"Logged in as **{st.session_state['player_display_name']}**")
if "current_lobby_name" in st.session_state:
    st.caption(f"Current lobby: **{st.session_state['current_lobby_name']}**")
else:
    st.info("Head to the Lobby page to create or join a lobby.")
st.caption("Use the + below to add a check-in, or open Leaderboard and Photo history.")
