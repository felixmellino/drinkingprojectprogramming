"""Browse joined lobbies, create a competition, or join with an invite code."""

from zoneinfo import available_timezones

import streamlit as st

import data.db as db
from core.lobbies import create_lobby, join_lobby
from lobby_ui import show_lobbies
from team_ui import dismiss_lobby_dialog
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

@st.dialog("Create lobby", width="large", on_dismiss=dismiss_lobby_dialog)
def create_lobby_dialog():
    mode = st.radio("Competition mode", ["individual", "team"], format_func=str.title, horizontal=True)
    count = capacity = assignment = None
    if mode == "team":
        count = st.number_input("Number of teams", min_value=2, max_value=16, value=2)
        capacity = st.number_input("Players per team", min_value=1, max_value=20, value=2)
        assignment = st.radio("Team assignment", ["manual", "random"],
                              format_func=lambda v: "Players choose" if v == "manual" else "Random", horizontal=True)
        st.caption("Teams start as Team 1, Team 2, etc. Members can edit their team's name and picture. Team totals decide the leaderboard and territory ownership.")
    with st.form("create_lobby_form"):
        lobby_name = st.text_input("Lobby name").strip()
        length_choice = st.radio("Lobby duration", options=["1_week", "1_month", "3_months"],
                                 format_func=lambda value: value.replace("_", " "), horizontal=True)
        timezone_name = st.selectbox("Lobby timezone", zones, index=zones.index("Europe/Lisbon"))
        test_mode = st.checkbox("Test season: Wednesday 08:00–Sunday 18:00", key="create_test_season",
                                help="For QA lobbies only. The selected rules stay fixed for this season.")
        st.caption("Normal scoring: Thu 18:00–Sun 18:00. Test scoring: Wed 08:00–Sun 18:00. Both use the lobby timezone. When the duration ends, this lobby closes permanently.")
        create_submitted = st.form_submit_button("Create lobby")

    if create_submitted:
        if not lobby_name:
            st.error("Lobby name is required.")
        else:
            try:
                lobby = create_lobby(lobby_name, mode, team_count=count, team_capacity=capacity, team_assignment=assignment)
                db.insert_lobby(lobby)
                membership = join_lobby(player_id, lobby.invite_code, [lobby], [])
                db.insert_membership(membership)
            except (APIError, RequestError, RuntimeError, ValueError):
                st.error("Lobby creation could not be confirmed. Close this window and refresh your lobbies before trying again. Team lobbies require migration 010.")
                return
            st.session_state["current_lobby_mode"] = lobby.game_mode
            st.session_state["current_membership_id"] = membership.id
            st.session_state["current_lobby_id"] = lobby.id
            st.session_state["current_lobby_name"] = lobby.name
            try:
                season = db.start_scoring_season(player_id, lobby.id, length_choice, timezone_name,
                                                 **({"test_mode": True} if test_mode else {}))
            except (APIError, RequestError, RuntimeError, CheckinRejected):
                st.error("The lobby was created, but its scoring season could not start. Ask the Data owner to apply migration 005, then use Retry lobby setup on its card.")
                st.stop()

            st.session_state["current_membership_id"] = membership.id
            st.session_state["current_lobby_id"] = lobby.id
            st.session_state["current_lobby_name"] = lobby.name
            st.session_state["current_season_id"] = season.id
            st.session_state["_lobby_notice"] = f"Lobby created! Invite code: {lobby.invite_code}"
            dismiss_lobby_dialog()
            st.rerun()

@st.dialog("Join with a code", on_dismiss=dismiss_lobby_dialog)
def join_lobby_dialog():
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
                try:
                    db.insert_membership(membership)
                except (APIError, RequestError, RuntimeError):
                    st.error("Could not join this lobby. It may be full or finished; refresh and try again.")
                    st.stop()
            lobby = next(l for l in db.list_lobbies() if l.id == membership.lobby_id)
            st.session_state["current_lobby_mode"] = lobby.game_mode
            seasons = db.list_seasons_for_lobby(lobby.id)

            st.session_state["current_membership_id"] = membership.id
            st.session_state["current_lobby_id"] = lobby.id
            st.session_state["current_lobby_name"] = lobby.name
            chosen_season = latest_season(seasons)
            st.session_state["current_season_id"] = chosen_season.id if chosen_season else None
            st.session_state["_lobby_notice"] = f"Joined {lobby.name}!"
            dismiss_lobby_dialog()
            st.rerun()


create_action, join_action = st.columns(2)
with create_action:
    if st.button("Create a lobby", key="open_create_lobby", type="primary", width="stretch"):
        st.session_state["_lobby_dialog"] = "create"
with join_action:
    if st.button("Join with a code", key="open_join_lobby", width="stretch"):
        st.session_state["_lobby_dialog"] = "join"

st.divider()
show_lobbies(player_id, memberships)

if st.session_state.get("_lobby_dialog") == "create":
    create_lobby_dialog()
elif st.session_state.get("_lobby_dialog") == "join":
    join_lobby_dialog()
