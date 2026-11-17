"""Create a lobby (with a season length), join one by invite code, or
switch between lobbies you've already joined."""

from datetime import datetime

import streamlit as st

import data.db as db
from core.lobbies import create_lobby, create_season, join_lobby
from shared import require_login, show_logged_in_as

player_id = require_login()
show_logged_in_as()

st.title("Lobby")

memberships = db.list_memberships_for_player(player_id)
if memberships:
    lobbies_by_id = {lobby.id: lobby for lobby in db.list_lobbies()}
    st.subheader("Switch lobby")
    chosen_id = st.selectbox(
        "Your lobbies",
        options=[m.lobby_id for m in memberships],
        format_func=lambda lid: lobbies_by_id[lid].name if lid in lobbies_by_id else lid,
    )
    if st.button("Make active"):
        chosen_membership = next(m for m in memberships if m.lobby_id == chosen_id)
        seasons = db.list_seasons_for_lobby(chosen_id)
        st.session_state["current_membership_id"] = chosen_membership.id
        st.session_state["current_lobby_id"] = chosen_id
        st.session_state["current_lobby_name"] = lobbies_by_id[chosen_id].name
        st.session_state["current_season_id"] = seasons[0].id if seasons else None
        st.success(f"Active lobby set to {lobbies_by_id[chosen_id].name}.")

st.divider()

create_tab, join_tab = st.tabs(["Create a lobby", "Join with a code"])

with create_tab:
    with st.form("create_lobby_form"):
        lobby_name = st.text_input("Lobby name")
        length_choice = st.radio("Season length", options=["1_week", "1_month", "3_months"], horizontal=True)
        create_submitted = st.form_submit_button("Create lobby")

    if create_submitted:
        if not lobby_name:
            st.error("Lobby name is required.")
        else:
            lobby = create_lobby(lobby_name)
            db.insert_lobby(lobby)
            membership = join_lobby(player_id, lobby.invite_code, [lobby], [])
            db.insert_membership(membership)
            season = create_season(lobby.id, length_choice, datetime.now())
            db.insert_season(season)

            st.session_state["current_membership_id"] = membership.id
            st.session_state["current_lobby_id"] = lobby.id
            st.session_state["current_lobby_name"] = lobby.name
            st.session_state["current_season_id"] = season.id
            st.success(f"Lobby created! Invite code: **{lobby.invite_code}**")

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
            st.session_state["current_season_id"] = seasons[0].id if seasons else None
            st.success(f"Joined {lobby.name}!")
