"""Map: the 12 territories coloured by owner, the points needed to take each
one, and where you are right now (followed automatically, R-L01/R-L04).
Only the current lobby's season counts."""

import streamlit as st
from streamlit.errors import StreamlitInvalidLayoutContextError
import base64
from html import escape
from math import ceil
from time import monotonic
from httpx import RequestError
from postgrest.exceptions import APIError

import data.db as db
from action_feedback import explain
from core.action_feedback import location_problem
import map_ui
from profile_picture_ui import load_pictures, PICTURE_ERRORS
from core.constants import MAX_GPS_ACCURACY_M
from core.location import evaluate_location
from core.scoring_v1 import TERRITORY_MULTIPLIER, current_time
from parallel import run_parallel
from phone_location import current_location, track_location
from shared import get_territories, require_active_membership, require_login, show_logged_in_as

player_id = require_login()
show_logged_in_as()
membership_id, lobby_id, season_id = require_active_membership()
season = st.session_state.get("_validated_season")
boost_enabled = season is not None and (season.scoring_rules or {}).get("territory_boost") is True

map_ui.load_styles()

try:
    territories = get_territories()
    entries, memberships, players = run_parallel(
        lambda: db.list_drink_entries(season_id),
        lambda: db.list_memberships_for_lobby(lobby_id, include_left=True),
        db.list_public_usernames)
    players_by_id = {p['id']: p['display_name'] for p in players}
except (APIError, RequestError, RuntimeError):
    st.error("We couldn't load the map. Reload the page to try again.")
    st.stop()

names = {m.id: players_by_id.get(m.player_id, "Unknown player") for m in memberships}
team_mode = False
teams = []
if st.session_state.get("current_lobby_mode") == "team" or any(e.team_id for e in entries):
    team_mode = True
    try:
        teams = db.list_lobby_teams(player_id, lobby_id)
        names = {t.id: t.name for t in teams}
    except (APIError, RequestError, RuntimeError, PermissionError):
        st.error("Teams could not be loaded. Reload to try again.")
        st.stop()
    membership_id = next((m.team_id for m in memberships if m.id == membership_id), None)
rows = map_ui.territory_rows(territories, entries, membership_id, names)

# Load only owners' pictures, using the existing audience checks on every render.
owner_ids = {row["owner_id"] for row in rows if row["owner_id"]}
pictures = {}
if team_mode:
    for team in teams:
        if team.id in owner_ids and team.photo_base64:
            try:
                pictures[team.id] = base64.b64decode(team.photo_base64, validate=True)
            except ValueError:
                pass  # A missing/unreadable photo still has an initials badge.
else:
    if st.session_state.get("credential_version"):
        owners = [m for m in memberships if m.id in owner_ids]
        try:
            fetched = load_pictures(player_id, [m.player_id for m in owners])
            pictures = {m.id: fetched[m.player_id] for m in owners if m.player_id in fetched}
        except (*PICTURE_ERRORS, PermissionError, ValueError):
            pass  # An unavailable picture still has the existing initials badge.

# HUD floating over the top of the map: lobby and score. Location is switched on
# in Profile; here the phone's position is only followed (invisible tracker, the
# same as on Check-in), before current_location() reads the newest reading.
with st.container(key="game_hud"):
    map_ui.hud(st.session_state.get("current_lobby_name", "Your lobby"), rows)
track_location()

# Where am I? Decides where the map starts and the "You are here" note.
location, accuracy_m, problem = current_location()
usable_location = location is not None and accuracy_m <= MAX_GPS_ACCURACY_M
here = None
if usable_location:
    result, territory_id = evaluate_location(location, accuracy_m, territories)
    here = next((row for row in rows if row["id"] == territory_id), None) if result == "matched" else None

# Selection lives in the session, so the map tap, the list and the close handle
# all change the same thing. Nothing is selected by default.
known = {row["id"] for row in rows}
if st.session_state.get("map_selected") not in known:
    st.session_state.pop("map_selected", None)
if st.session_state.get("map_focus") not in known:
    st.session_state.pop("map_focus", None)


def rerun_map():
    """Rerun only the map fragment when Streamlit allows it (a tap starts a
    fragment rerun); on a full page run, rerun the page."""
    try:
        st.rerun(scope="fragment")
    except StreamlitInvalidLayoutContextError:
        st.rerun()


def reset_map_selection():
    """The map keeps its own tap selection (and solid highlight). A new key
    redraws it fresh, so closing the card also clears the highlight and the
    same area can be tapped again."""
    st.session_state["map_reset"] = st.session_state.get("map_reset", 0) + 1
    st.session_state["map_last_tap"] = None


def current_map_boost():
    if not boost_enabled:
        return None
    context = (player_id, season_id)
    saved_context, checked_at, active_boost = st.session_state.get("map_territory_boost", (None, 0, None))
    polled_at = monotonic()
    if context != saved_context or polled_at - checked_at >= 9:
        try:
            active_boost = db.active_territory_boost(player_id, season_id)
        except (APIError, RequestError, PermissionError, RuntimeError):
            active_boost = None
        st.session_state["map_territory_boost"] = (context, polled_at, active_boost)
    if active_boost and active_boost[0] in known:
        territory_id, ends_at = active_boost
        remaining = ceil((ends_at - current_time()).total_seconds())
        if remaining > 0:
            minutes, seconds = divmod(remaining, 60)
            return territory_id, f"{TERRITORY_MULTIPLIER:g}x\n{minutes:02d}:{seconds:02d}"
    return None


initial_boost = current_map_boost()

# Taps and clock ticks reuse the existing rows without replaying the scores.
@st.fragment(run_every=(1 if initial_boost else 10) if boost_enabled else None)
def map_and_card():
    selected_id = st.session_state.get("map_selected")
    boost = current_map_boost()
    if bool(boost) != bool(initial_boost):
        st.rerun()  # Switch between idle polling and the live countdown.
    default_focus = map_ui.ME if usable_location else (boost[0] if boost else "Lisbon")
    focus = st.session_state.get("map_focus") or default_focus
    with st.container(key="game_map"):
        tapped = map_ui.render_map(rows, location if usable_location else None, accuracy_m, focus,
                                   pictures=pictures, selected=selected_id, boost=boost,
                                   context=f"{lobby_id}:{season_id}:{membership_id}:{focus}:"
                                           f"{st.session_state.get('map_reset', 0)}")
    # A new tap on the map (or on empty space) changes the selection; tapping
    # the selected area again closes it.
    if tapped != st.session_state.get("map_last_tap"):
        st.session_state["map_last_tap"] = tapped
        new = None if tapped == selected_id else tapped
        if new != selected_id:
            st.session_state["map_selected"] = new
            rerun_map()

    selected = next((row for row in rows if row["id"] == selected_id), None)
    with st.container(key="game_card"):
        if boost:
            boosted_name = next(row["name"] for row in rows if row["id"] == boost[0])
            multiplier, time_left = boost[1].splitlines()
            st.html(f'<span class="sr-only" role="timer">{escape(boosted_name)} '
                    f'{multiplier} boost expires in {time_left}</span>')
        if map_ui.selection_card(selected, here):       # the grey handle closes the card
            st.session_state.pop("map_selected", None)
            reset_map_selection()
            rerun_map()
        if not usable_location and st.button("Location help", key="map_location_help", type="tertiary"):
            explain(location_problem(problem, accuracy_m) or "Your position could not be verified. Turn Location off and on in Profile, then return to the map.")
        map_ui.all_territories_button(rows)
    picked = map_ui.territory_list(rows, lobby_name=st.session_state.get("current_lobby_name", ""),
                                   team_mode=team_mode)
    if picked:                                          # a name in the list: select it and fly there
        st.session_state["map_selected"] = picked
        st.session_state["map_focus"] = picked
        reset_map_selection()
        rerun_map()


map_and_card()
