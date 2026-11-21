"""WeGoPub entry point: returning players open on the Map.

Account forms live in account_ui.py. Successful registration goes directly
to Lobbies during sign-in.
"""

import streamlit as st

from shared import require_login

st.set_page_config(page_title="WeGoPub", page_icon=":material/sports_bar:")
# Existing sessions go straight to Map, whose own bootstrap freshly validates
# credentials and membership. Avoid validating/loading the same context twice.
if "player_id" not in st.session_state:
    require_login()
st.switch_page("pages/5_Map.py")  # the start screen is the Map
