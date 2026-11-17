"""Season leaderboard + territory standings (a plain list for now --
the interactive map is a later page)."""

import streamlit as st

import data.db as db
from core.leaderboard import season_leaderboard
from core.territories import territory_owner, territory_standings
from core.scoring_v1 import format_points
from shared import get_territories, require_active_membership, require_login, show_logged_in_as

require_login()
show_logged_in_as()
_membership_id, lobby_id, season_id = require_active_membership()

st.title("Standings")

entries = db.list_drink_entries(season_id)

# membership_id -> display_name, for showing names instead of raw ids.
memberships = db.list_memberships_for_lobby(lobby_id)
players_by_id = {p.id: p.display_name for p in db.list_players()}
names_by_membership = {m.id: players_by_id.get(m.player_id, "?") for m in memberships}

st.subheader("Season leaderboard")
if any(entry.rule_version == "v1" for entry in entries):
    st.caption("Season points include your drinks and 25% income from other players in your territories. Territory points include only your drinks.")
leaderboard = season_leaderboard(entries)
if not leaderboard:
    st.info("No points logged yet this season.")
else:
    st.table(
        [
            {"Rank": rank, "Player": names_by_membership.get(membership_id, "?"), "Points": format_points(points)}
            for rank, (membership_id, points) in enumerate(leaderboard, start=1)
        ]
    )

st.subheader("Territories")
territories = get_territories()
if not territories:
    st.info("No territories have been set up yet.")
for territory in territories:
    owner_id = territory_owner(entries, territory.id)
    standings = territory_standings(entries, territory.id)
    st.write(f"**{territory.name}**")
    if owner_id:
        st.write(f"Owner: {names_by_membership.get(owner_id, '?')}")
    else:
        st.write("No confirmed drinks here yet.")
    if standings:
        st.table(
            [{"Player": names_by_membership.get(membership_id, "?"), "Points": points} for membership_id, points in standings]
        )
