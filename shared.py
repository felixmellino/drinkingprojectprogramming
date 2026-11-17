"""Small helpers shared by the Streamlit pages. Lives at the project root
(not inside pages/) so Streamlit's multipage navigation doesn't list it as
its own page.

These functions only glue Streamlit + data/db.py + core/ together -- they
contain no game rules themselves.
"""

import streamlit as st


def require_login() -> str:
    """Stop the page and prompt a login if nobody is logged in. Returns
    the logged-in player's id otherwise."""
    if "player_id" not in st.session_state:
        st.warning("Please log in on the Profile page first.")
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
