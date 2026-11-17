"""Create an account, or log in."""

import streamlit as st

import data.db as db
from core.auth import authenticate
from core.lobbies import create_player

st.title("Profile")

if "player_id" in st.session_state:
    st.success(f"Logged in as **{st.session_state['player_display_name']}**")
    st.caption(f"Name: {st.session_state.get('player_first_name', '')} {st.session_state.get('player_last_name', '')} (private)")
    if st.button("Log out"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    st.stop()

log_in_tab, create_tab = st.tabs(["Log in", "Create account"])

with log_in_tab:
    with st.form("login_form"):
        username = st.text_input("Username")
        pin = st.text_input("PIN", type="password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        player = authenticate(username, pin, db.list_players())
        if player is None:
            st.error("Username or PIN is incorrect.")
        else:
            st.session_state["player_id"] = player.id
            st.session_state["player_display_name"] = player.display_name
            st.session_state["player_first_name"] = player.first_name
            st.session_state["player_last_name"] = player.last_name
            st.rerun()

with create_tab:
    st.caption("Only your username is visible to other players. Your real name stays private.")
    with st.form("create_account_form"):
        first_name = st.text_input("First name (private)")
        last_name = st.text_input("Last name (private)")
        username = st.text_input("Username (public)")
        pin = st.text_input("Choose a PIN", type="password")
        pin_confirm = st.text_input("Confirm PIN", type="password")
        create_submitted = st.form_submit_button("Create account")

    if create_submitted:
        if not first_name or not last_name or not username or not pin:
            st.error("All fields are required.")
        elif pin != pin_confirm:
            st.error("PINs don't match.")
        elif any(p.display_name == username for p in db.list_players()):
            st.error("That username is already taken.")
        else:
            player = create_player(username, first_name, last_name, pin)
            db.insert_player(player)
            st.success("Account created -- log in on the other tab.")
