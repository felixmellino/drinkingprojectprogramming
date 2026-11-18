"""Create a lobby (with a season length), join one by invite code, or
switch between lobbies you've already joined."""

from datetime import datetime, timezone
from zoneinfo import available_timezones

import streamlit as st

import data.db as db
from core.lobbies import create_lobby, join_lobby
from core.checkins import CheckinRejected
from core.scoring_v1 import utc
from httpx import RequestError
from postgrest.exceptions import APIError
from shared import require_login, show_logged_in_as

player_id = require_login()
show_logged_in_as()

st.title("Lobby")

zones = sorted(available_timezones())


def choose_season(seasons):
    now = datetime.now(timezone.utc)
    return next((s for s in seasons if utc(s.starts_at) <= now < utc(s.ends_at)), seasons[0] if seasons else None)

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
        chosen_season = choose_season(seasons)
        st.session_state["current_season_id"] = chosen_season.id if chosen_season else None
        st.success(f"Active lobby set to {lobbies_by_id[chosen_id].name}.")

st.divider()

create_tab, join_tab = st.tabs(["Create a lobby", "Join with a code"])

with create_tab:
    with st.form("create_lobby_form"):
        lobby_name = st.text_input("Lobby name").strip()
        length_choice = st.radio("Season length", options=["1_week", "1_month", "3_months"], horizontal=True)
        timezone_name = st.selectbox("Lobby timezone", zones, index=zones.index("Europe/Lisbon"))
        st.caption("New season: Thu 18:00–Sun 18:00 in this timezone. Scoring rules and timezone stay fixed for the season.")
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
                st.error("The lobby was created, but its scoring season could not start. Ask the Data owner to apply migration 005, then start the season below.")
                st.stop()

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
            chosen_season = choose_season(seasons)
            st.session_state["current_season_id"] = chosen_season.id if chosen_season else None
            st.success(f"Joined {lobby.name}!")

if st.session_state.get("current_lobby_id"):
    st.divider()
    st.subheader("Seasons")
    active_lobby = st.session_state["current_lobby_id"]
    lobby_seasons = db.list_seasons_for_lobby(active_lobby)
    if lobby_seasons:
        selected = st.selectbox("View season", lobby_seasons,
            format_func=lambda s: f"{s.starts_at:%d %b %Y} – {s.ends_at:%d %b %Y} · {s.scoring_version}")
        if st.button("Select this season"):
            st.session_state["current_season_id"] = selected.id
            st.success("Season selected. Open Check in, Standings or Lobby photos.")
    still_running = any(utc(s.ends_at) > datetime.now(timezone.utc) for s in lobby_seasons)
    if still_running:
        st.caption("Existing season settings and history are preserved. A new season can start after the current one ends.")
    else:
        with st.form("start_next_season"):
            next_length = st.radio("Next season length", ["1_week", "1_month", "3_months"], horizontal=True)
            inherited_zone = lobby_seasons[0].timezone_name if lobby_seasons else "Europe/Lisbon"
            next_zone = st.selectbox("Next season timezone", zones, index=zones.index(inherited_zone) if inherited_zone in zones else zones.index("Europe/Lisbon"))
            start = st.form_submit_button("Start next scoring season")
        if start:
            try:
                new_season = db.start_scoring_season(player_id, active_lobby, next_length, next_zone)
            except PermissionError:
                st.error("Join this lobby before starting its season.")
            except CheckinRejected:
                st.error("A season is already running or these settings are invalid. Refresh and try again.")
            except (APIError, RequestError, RuntimeError):
                st.error("Season setup is unavailable. Ask the Data owner to check migration 005.")
            else:
                st.session_state["current_season_id"] = new_season.id
                st.success("New season started with fresh standings and unclaimed territories.")
