"""The season ranking and territory accounts, using the core's existing order."""

import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError

import data.db as db
from core.leaderboard import season_leaderboard
from core.lobby_overview import lobby_status
from core.scoring_v1 import current_time, replay_season
from core.territories import territory_owner, territory_standings
from drink_entry_ui import context_line, page_header, section_heading
from lobby_selection import leaderboard_fallback
import standings_ui
from shared import get_territories, require_active_membership, require_login, show_logged_in_as

player_id = require_login()
show_logged_in_as()

page_header("Leaderboard", "Your place in the season. Every point and territory, together.", standings=True)
standings_ui.load_styles()

st.button("Refresh standings")
try:
    if st.session_state.get("current_membership_id") and st.session_state.get("current_season_id"):
        membership_id, lobby_id, season_id = require_active_membership()
        lobby_name = st.session_state.get("current_lobby_name", "Your lobby")
        lobby_mode = st.session_state.get("current_lobby_mode")
        season = st.session_state.get("_validated_season")
    else:
        fallback = leaderboard_fallback(player_id)
        if fallback is None:
            st.info("There are no standings to show yet. Join a lobby with a season to see its leaderboard.")
            if st.button("Open Lobby"):
                st.switch_page("pages/2_Lobby.py")
            st.stop()
        lobby, member, season = fallback
        membership_id, lobby_id, season_id = member.id, lobby.id, season.id
        member, season = db.membership_context(player_id, membership_id, lobby_id, season_id)
        if member is None or season is None:
            st.warning("That lobby or season is no longer available. Use Refresh standings to try again.")
            st.stop()
        lobby_name, lobby_mode = lobby.name, lobby.game_mode
    entries = db.list_drink_entries(season_id)
    memberships = db.list_memberships_for_lobby(lobby_id)
    players_by_id = {p.id: p.display_name for p in db.list_players()}
except (APIError, RequestError, RuntimeError):
    st.error("We couldn't load the standings. Use Refresh standings to try again.")
    st.stop()

names = {m.id: players_by_id.get(m.player_id, "Unknown player") for m in memberships}
team_mode = lobby_mode == "team" or any(e.team_id for e in entries)
if team_mode:
    try:
        teams = db.list_lobby_teams(player_id, lobby_id)
    except (APIError, RequestError, RuntimeError, PermissionError):
        st.error("Teams could not be loaded. Refresh standings to try again.")
        st.stop()
    names = {t.id: t.name for t in teams}
    membership_id = next((m.team_id for m in memberships if m.id == membership_id), None)
    if not membership_id:
        st.info("Open this lobby on the Lobby page and join a team before checking in.")
snapshot = replay_season(entries) if any(e.rule_version == "v1" for e in entries) else None
leaderboard = snapshot.season_rows() if snapshot else season_leaderboard(entries)
status = lobby_status(season, current_time()) if season else "active"
if status == "past":
    st.caption("Finished season · Final standings")
elif status == "upcoming":
    st.caption("Upcoming season")
context_line(lobby_name,
             f"{len(memberships)} members · {len(leaderboard)} ranked this season")

# Reuse the same territory accounts for the summary and cards. A territory
# service failure must not hide a successfully loaded season ranking.
territory_data = []
owner_counts = {}
territories_available = True
try:
    for territory in get_territories():
        owner = snapshot.owners.get(territory.id) if snapshot else territory_owner(entries, territory.id)
        rows = snapshot.territory_rows(territory.id) if snapshot else territory_standings(entries, territory.id)
        territory_data.append((territory, owner, rows))
        if owner:
            owner_counts[owner] = owner_counts.get(owner, 0) + 1
    for member, _ in leaderboard:
        owner_counts.setdefault(member, 0)
except (APIError, RequestError, RuntimeError):
    territories_available = False
    territory_data = []
    owner_counts = {}

own_rank = next((rank for rank, (member, _) in enumerate(leaderboard, start=1) if member == membership_id), None)
own_points = next((points for member, points in leaderboard if member == membership_id), 0)
owned = owner_counts.get(membership_id, 0) if territories_available else None
standings_ui.personal_summary(own_rank, own_points, owned, len(leaderboard), team_mode=team_mode)

section_heading("01", "Season leaderboard", "Ranked by combined team points. Your team is marked YOUR TEAM." if team_mode else "Ranked by total season points. Your row is marked YOU.")
if not leaderboard:
    st.info("No points logged yet this season.")
else:
    standings_ui.leaderboard(leaderboard, names, membership_id, owner_counts, team_mode=team_mode)
    st.caption("Equal points? The team who reached the score first ranks higher." if team_mode else "Equal points? The player who reached the score first ranks higher.")
if any(entry.rule_version == "v1" for entry in entries):
    st.caption("Team season points combine all members’ drinks and 25% income from rival teams. Territory points combine members’ base drink points." if team_mode else "Season points include your drinks and 25% income from other players in your territories. Territory points include only your drinks.")

section_heading("02", "Territories", "Local standings use base drink points. Owner income stays in the season total.")
if not territories_available:
    st.warning("Territory standings are unavailable. Use Refresh standings to try again.")
elif not territory_data:
    st.info("No territories have been set up yet.")
else:
    standings_ui.territory_cards(territory_data, names, membership_id)
