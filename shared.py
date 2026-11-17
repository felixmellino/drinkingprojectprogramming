"""Small helpers shared by the Streamlit pages. Lives at the project root
(not inside pages/) so Streamlit's multipage navigation doesn't list it as
its own page.

These functions only glue Streamlit + data/db.py + core/ together -- they
contain no game rules themselves.
"""

import streamlit as st

import data.db as db
from account_ui import show_accounts
from device_login import sync_storage, set_identity, queue_storage
from postgrest.exceptions import APIError
from httpx import RequestError


def require_login() -> str:
    """Stop the page and prompt a login if nobody is logged in. Returns
    the logged-in player's id otherwise."""
    token = sync_storage()
    if token is not None and not st.session_state.get("_remember_attempted"):
        if token:
            try:
                player = db.get_remembered_player(token)
            except (APIError, RuntimeError, OSError, RequestError):
                st.error("Account service is unavailable. Please try again later.")
                st.stop()
            if player:
                set_identity(player)
                st.session_state["_device_token"] = token
            else:
                queue_storage("clear")
                st.rerun()
        st.session_state["_remember_attempted"] = True
    if "player_id" in st.session_state:
        try:
            player = db.get_player(st.session_state["player_id"])
        except (APIError, RuntimeError, OSError, RequestError):
            st.error("Account service is unavailable. Please try again later.")
            st.stop()
        if not player or not player.email or player.pin_hash != st.session_state.get("credential_version"):
            st.session_state.clear()
            st.session_state["_remember_attempted"] = True
            queue_storage("clear")
            st.info("Please log in again.")
    if "player_id" not in st.session_state:
        show_accounts()
        st.stop()
    return st.session_state["player_id"]


def require_active_membership() -> tuple[str, str, str]:
    """Stop the page with a message if no lobby is selected yet. Returns
    (membership_id, lobby_id, season_id) otherwise."""
    if "current_membership_id" not in st.session_state:
        st.info("Create or join a lobby on the Lobby page first.")
        st.stop()
    return (
        st.session_state["current_membership_id"],
        st.session_state["current_lobby_id"],
        st.session_state["current_season_id"],
    )


def show_logged_in_as():
    st.sidebar.caption(f"Logged in as **{st.session_state.get('player_display_name', '?')}**")
    if "current_lobby_name" in st.session_state:
        st.sidebar.caption(f"Lobby: **{st.session_state['current_lobby_name']}**")
