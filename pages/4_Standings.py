"""The season ranking and territory accounts, using the core's existing order."""

import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError

import data.db as db
from core.leaderboard import season_leaderboard
from core.territories import territory_owner, territory_standings
from core.scoring_v1 import replay_season
from drink_entry_ui import page_header
import standings_ui
from shared import get_territories, require_active_membership, require_login, show_logged_in_as

player_id = require_login()
show_logged_in_as()
membership_id, lobby_id, season_id = require_active_membership()

page_header("Leaderboard", "Your place in the season. Every point and territory, together.")
standings_ui.load_styles()

st.button("Refresh standings")
try:
    entries = db.list_drink_entries(season_id)
    memberships = db.list_memberships_for_lobby(lobby_id)
    players_by_id = {p.id: p.display_name for p in db.list_players()}
except (APIError, RequestError, RuntimeError):
    st.error("We couldn't load the standings. Use Refresh standings to try again.")
    st.stop()

names = {m.id: players_by_id.get(m.player_id, "Unknown player") for m in memberships}
team_mode = st.session_state.get("current_lobby_mode") == "team" or any(e.team_id for e in entries)
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

# Reuse the same territory accounts for the pills. A territory service
# failure must not hide a successfully loaded season ranking.
territory_data = []
territories_available = True
try:
    for territory in get_territories():
        owner = snapshot.owners.get(territory.id) if snapshot else territory_owner(entries, territory.id)
        rows = snapshot.territory_rows(territory.id) if snapshot else territory_standings(entries, territory.id)
        territory_data.append((territory, owner, rows))
except (APIError, RequestError, RuntimeError):
    territories_available = False
    territory_data = []

if not leaderboard:
    st.info("No points logged yet this season.")
else:
    standings_ui.leaderboard(leaderboard, names, membership_id, team_mode=team_mode)
    st.caption("Equal points? The team who reached the score first ranks higher." if team_mode else "Equal points? The player who reached the score first ranks higher.")
if any(entry.rule_version == "v1" for entry in entries):
    st.caption("Team season points combine all members’ drinks and 25% income from rival teams. Territory points combine members’ base drink points." if team_mode else "Season points include your drinks and 25% income from other players in your territories. Territory points include only your drinks.")

if not territories_available:
    st.warning("Territory standings are unavailable. Use Refresh standings to try again.")
elif not territory_data:
    st.info("No territories have been set up yet.")
else:
    standings_ui.territory_pills(territory_data, names, membership_id)
