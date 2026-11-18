"""The season ranking and territory accounts, using the core's existing order."""

import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError

import data.db as db
from core.leaderboard import season_leaderboard
from core.territories import territory_owner, territory_standings
from drink_entry_ui import context_line, page_header, section_heading
import standings_ui
from shared import get_territories, require_active_membership, require_login, show_logged_in_as

require_login()
show_logged_in_as()
membership_id, lobby_id, season_id = require_active_membership()

page_header("Leaderboard", "Your place in the season. Every point and territory, together.", standings=True)
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
leaderboard = season_leaderboard(entries)
context_line(st.session_state.get("current_lobby_name", "Your lobby"),
             f"{len(memberships)} members · {len(leaderboard)} ranked this season")

# Reuse the same territory accounts for the summary and cards. A territory
# service failure must not hide a successfully loaded season ranking.
territory_data = []
owner_counts = {}
territories_available = True
try:
    for territory in get_territories():
        owner = territory_owner(entries, territory.id)
        rows = territory_standings(entries, territory.id)
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
standings_ui.personal_summary(own_rank, own_points, owned, len(leaderboard))

section_heading("01", "Season leaderboard", "Ranked by total season points. Your row is marked YOU.")
if not leaderboard:
    st.info("No points logged yet this season.")
else:
    standings_ui.leaderboard(leaderboard, names, membership_id, owner_counts)
    st.caption("Equal points? The player who reached the score first ranks higher.")
if any(entry.rule_version == "v1" for entry in entries):
    st.caption("Season points include your drinks and 25% income from other players in your territories. Territory points include only your drinks.")

section_heading("02", "Territories", "Local standings use base drink points. Owner income stays in the season total.")
if not territories_available:
    st.warning("Territory standings are unavailable. Use Refresh standings to try again.")
elif not territory_data:
    st.info("No territories have been set up yet.")
else:
    standings_ui.territory_cards(territory_data, names, membership_id)
