"""WeGoPub entry point: log in, then open on the Map -- no rules, no DB calls.

Actual login/account creation lives in account_ui.py, to keep this
file small and avoid everyone colliding on it as the team adds pages.
"""

import streamlit as st

from shared import require_login

st.set_page_config(page_title="WeGoPub", page_icon=":material/sports_bar:")
# Existing sessions go straight to Map, whose own bootstrap freshly validates
# credentials and membership. Avoid validating/loading the same context twice.
if "player_id" not in st.session_state:
    require_login()
st.switch_page("pages/5_Map.py")  # the start screen is the Map
