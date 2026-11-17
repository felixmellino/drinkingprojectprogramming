"""WeGoPub entry point -- nav shell only, no rules, no DB calls.

Actual login/account creation lives on pages/1_Profile.py, to keep this
file small and avoid everyone colliding on it as the team adds pages.
"""

import streamlit as st

st.set_page_config(page_title="WeGoPub", page_icon="🍺")
st.title("🍺 WeGoPub")

if "player_id" in st.session_state:
    st.success(f"Logged in as **{st.session_state['player_display_name']}**")
    if "current_lobby_name" in st.session_state:
        st.caption(f"Current lobby: **{st.session_state['current_lobby_name']}**")
    else:
        st.info("Head to the Lobby page to create or join a lobby.")
else:
    st.info("Head to the Profile page to create an account or log in.")

st.caption("Use the sidebar to navigate: Profile, Lobby, Check in, Standings.")
