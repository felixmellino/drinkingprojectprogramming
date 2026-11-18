"""Browse joined lobbies, create a competition, or join with an invite code."""

from zoneinfo import available_timezones

import streamlit as st

import data.db as db
from core.lobbies import create_lobby, join_lobby
from lobby_ui import show_lobbies
from core.checkins import CheckinRejected
from core.lobby_overview import latest_season
from httpx import RequestError
from postgrest.exceptions import APIError
from shared import require_login, show_logged_in_as

player_id = require_login()
show_logged_in_as()

st.title("Lobby")

zones = sorted(available_timezones())


try:
    memberships = db.list_memberships_for_player(player_id)
except (APIError, RequestError, RuntimeError):
    st.error("Your lobbies could not be loaded. Refresh to try again.")
    st.stop()

show_lobbies(player_id, memberships)

st.divider()

create_tab, join_tab = st.tabs(["Create a lobby", "Join with a code"])

with create_tab:
    with st.form("create_lobby_form"):
        lobby_name = st.text_input("Lobby name").strip()
        length_choice = st.radio("Lobby duration", options=["1_week", "1_month", "3_months"],
                                 format_func=lambda value: value.replace("_", " "), horizontal=True)
        timezone_name = st.selectbox("Lobby timezone", zones, index=zones.index("Europe/Lisbon"))
        st.caption("Scoring opens Thu 18:00–Sun 18:00 in this timezone. When the duration ends, this lobby closes permanently.")
        create_submitted = st.form_submit_button("Create lobby")

    if create_submitted:
        if not lobby_name:
            st.error("Lobby name is required.")
        else:
            lobby = create_lobby(lobby_name)
            db.insert_lobby(lobby)
            membership = join_lobby(player_id, lobby.invite_code, [lobby], [])
            db.insert_membership(membership)
            st.session_state["current_membership_id"] = membership.id
            st.session_state["current_lobby_id"] = lobby.id
            st.session_state["current_lobby_name"] = lobby.name
            try:
                season = db.start_scoring_season(player_id, lobby.id, length_choice, timezone_name)
            except (APIError, RequestError, RuntimeError, CheckinRejected):
                st.error("The lobby was created, but its scoring season could not start. Ask the Data owner to apply migration 005, then use Retry lobby setup on its card.")
                st.stop()

            st.session_state["current_membership_id"] = membership.id
            st.session_state["current_lobby_id"] = lobby.id
            st.session_state["current_lobby_name"] = lobby.name
            st.session_state["current_season_id"] = season.id
            st.session_state["_lobby_notice"] = f"Lobby created! Invite code: {lobby.invite_code}"
            st.rerun()

with join_tab:
    with st.form("join_lobby_form"):
        invite_code = st.text_input("Invite code").strip().upper()
        join_submitted = st.form_submit_button("Join lobby")

    if join_submitted:
        try:
            membership = join_lobby(player_id, invite_code, db.list_lobbies(), memberships)
        except ValueError:
            st.error("That invite code doesn't match any lobby.")
        else:
            is_new = membership.id not in {m.id for m in memberships}
            if is_new:
                db.insert_membership(membership)
            lobby = next(l for l in db.list_lobbies() if l.id == membership.lobby_id)
            seasons = db.list_seasons_for_lobby(lobby.id)

            st.session_state["current_membership_id"] = membership.id
            st.session_state["current_lobby_id"] = lobby.id
            st.session_state["current_lobby_name"] = lobby.name
            chosen_season = latest_season(seasons)
            st.session_state["current_season_id"] = chosen_season.id if chosen_season else None
            st.session_state["_lobby_notice"] = f"Joined {lobby.name}!"
            st.rerun()
