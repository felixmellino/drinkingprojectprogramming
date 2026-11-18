"""Map: the 12 territories coloured by owner, the points needed to take each
one, and where you are right now (followed automatically, R-L01/R-L04).
Only the current lobby's season counts."""

import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError

import data.db as db
import map_ui
from core.constants import MAX_GPS_ACCURACY_M
from core.location import evaluate_location
from phone_location import current_location, track_location
from shared import get_territories, require_active_membership, require_login, show_logged_in_as

player_id = require_login()
show_logged_in_as()
membership_id, lobby_id, season_id = require_active_membership()

st.title("Map")
map_ui.load_styles()

track_location()
try:
    territories = get_territories()
    entries = db.list_drink_entries(season_id)
    memberships = db.list_memberships_for_lobby(lobby_id)
    players_by_id = {p.id: p.display_name for p in db.list_players()}
except (APIError, RequestError, RuntimeError):
    st.error("We couldn't load the map. Reload the page to try again.")
    st.stop()

names = {m.id: players_by_id.get(m.player_id, "Unknown player") for m in memberships}
if st.session_state.get("current_lobby_mode") == "team" or any(e.team_id for e in entries):
    try:
        names = {t.id: t.name for t in db.list_lobby_teams(player_id, lobby_id)}
    except (APIError, RequestError, RuntimeError, PermissionError):
        st.error("Teams could not be loaded. Reload to try again.")
        st.stop()
    membership_id = next((m.team_id for m in memberships if m.id == membership_id), None)
    st.caption("Team territories · Points and capture gaps combine all team members’ drinks.")
rows = map_ui.territory_rows(territories, entries, membership_id, names)

location, accuracy_m, problem = current_location()
if location is not None and accuracy_m <= MAX_GPS_ACCURACY_M:
    result, territory_id = evaluate_location(location, accuracy_m, territories)
    here = next((row for row in rows if row["id"] == territory_id), None)
    if result == "matched" and here:
        st.info(f"You are in **{map_ui.markdown_safe(here['name'])}**. {map_ui.markdown_safe(here['detail'])}")
    else:
        st.info("You are outside the game territories. Drinks here count for season points only.")
elif location is not None:
    st.caption(f"Your location is only accurate to about {accuracy_m:.0f} m, so it isn't used yet.")
elif problem == "denied":
    st.caption("Location access is blocked, so the map can't show where you are.")
else:
    st.caption("Finding your location…")

# Quick zoom: jump between the parts of the city that have territories.
# The map comes right after it so it's the first big thing on the page.
usable_location = location is not None and accuracy_m <= MAX_GPS_ACCURACY_M
options = ([map_ui.ME] if usable_location else []) + list(map_ui.AREAS) + [map_ui.ALL]
focus = st.segmented_control("Show", options, default=options[0], key="map_focus",
                             label_visibility="collapsed") or options[0]
if focus not in options:  # e.g. "Me" was picked but the location is gone now
    focus = options[0]

map_ui.render_map(rows, location if usable_location else None, accuracy_m, focus)
map_ui.render_summary(rows)
map_ui.territory_list(rows)
