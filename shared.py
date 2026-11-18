"""Small helpers shared by the Streamlit pages. Lives at the project root
(not inside pages/) so Streamlit's multipage navigation doesn't list it as
its own page.

These functions only glue Streamlit + data/db.py + core/ together -- they
contain no game rules themselves.
"""

import streamlit as st

import data.db as db
from core.models import Territory
from data.territory_file import load_territories
from account_ui import show_accounts
from device_login import sync_storage, set_identity, queue_storage
from postgrest.exceptions import APIError
from httpx import RequestError
from app_navigation import bottom_navigation


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
    bottom_navigation()
    return st.session_state["player_id"]


def require_active_membership() -> tuple[str, str, str]:
    """Stop the page with a message if no lobby is selected yet. Returns
    (membership_id, lobby_id, season_id) otherwise."""
    if "current_membership_id" not in st.session_state:
        st.info("Create or join a lobby on the Lobby page first.")
        st.stop()
    try:
        memberships = db.list_memberships_for_player(st.session_state["player_id"])
    except (APIError, RequestError, RuntimeError):
        st.error("Lobby access could not be checked. Try again.")
        st.stop()
    if not any(m.id == st.session_state["current_membership_id"]
               and m.lobby_id == st.session_state.get("current_lobby_id") for m in memberships):
        st.error("Your selected lobby membership is no longer available. Choose a lobby again.")
        st.stop()
    if not st.session_state.get("current_season_id"):
        st.info("Start or select a season on the Lobby page first.")
        st.stop()
    try:
        seasons = db.list_seasons_for_lobby(st.session_state["current_lobby_id"])
    except (APIError, RequestError, RuntimeError):
        st.error("Season access could not be checked. Try again.")
        st.stop()
    if not any(s.id == st.session_state["current_season_id"] for s in seasons):
        st.error("This season does not belong to the selected lobby. Choose a season again.")
        st.stop()
    return (
        st.session_state["current_membership_id"],
        st.session_state["current_lobby_id"],
        st.session_state["current_season_id"],
    )


@st.cache_resource(show_spinner=False)
def get_territories() -> list[Territory]:
    """The game's territories, read from data/territories.geojson (R-T01).

    The first call after the app starts also copies them into the database,
    because drink entries store a territory id that must exist there. The
    result is cached for the whole server process, so after editing the
    file, restart the app. If the database is unreachable the error is not
    cached and the next page load tries again."""
    territories = load_territories()
    db.upsert_territories(territories)
    return territories


def show_logged_in_as():
    st.sidebar.caption(f"Logged in as **{st.session_state.get('player_display_name', '?')}**")
    if "current_lobby_name" in st.session_state:
        st.sidebar.caption(f"Lobby: **{st.session_state['current_lobby_name']}**")
