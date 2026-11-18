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

# Where am I? Decides the bottom card and whether "Me" is offered.
location, accuracy_m, problem = current_location()
usable_location = location is not None and accuracy_m <= MAX_GPS_ACCURACY_M
here, status = None, "waiting"
if usable_location:
    result, territory_id = evaluate_location(location, accuracy_m, territories)
    here = next((row for row in rows if row["id"] == territory_id), None)
    status = "matched" if result == "matched" and here else "outside"
elif location is not None:
    status = "inaccurate"
elif problem == "denied":
    status = "denied"

# HUD floating over the top of the map: lobby, score, quick zoom.
with st.container(key="game_hud"):
    map_ui.hud(st.session_state.get("current_lobby_name", "Your lobby"), rows)
    options = ([map_ui.ME] if usable_location else []) + list(map_ui.AREAS) + [map_ui.ALL]
    focus = st.segmented_control("Show", options, default=options[0], key="map_focus",
                                 label_visibility="collapsed") or options[0]
    if focus not in options:  # e.g. "Me" was picked but the location is gone now
        focus = options[0]

with st.container(key="game_map"):
    map_ui.render_map(rows, location if usable_location else None, accuracy_m, focus)

# Card floating over the bottom of the map: where you are, and check in.
with st.container(key="game_card"):
    map_ui.location_card(here, status, accuracy_m)
    if st.button("Check in here", key="map_checkin", type="primary", icon=":material/add_location_alt:", width="stretch"):
        st.switch_page("pages/3_Check_in.py")

map_ui.legend()
with st.expander("All territories", icon=":material/list:"):
    map_ui.territory_list(rows)
