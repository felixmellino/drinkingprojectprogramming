"""Private account details and logout."""

import streamlit as st
from shared import require_login
import data.db as db
from device_login import log_out
from friends_ui import show_friends

player_id = require_login()
player = db.get_player(player_id)
st.title("Profile")
st.success(f"Logged in as **{player.display_name}**")
st.text(f"Name: {player.first_name} {player.last_name} (private)")
st.text(f"Email: {player.email} (private)")
if st.button("Log out"):
    log_out()

show_friends(player_id)
