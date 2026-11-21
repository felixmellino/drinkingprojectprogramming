"""Selected lobby activity, including lifetime medal promotions earned there."""

import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError

import activity_ui
import data.db as db
from core.activity import activity_events, with_promotions
from core.medals import lobby_promotions
from data.profile_history import load_stat_history
from core.scoring_v1 import current_time
from drink_entry_ui import page_header
from parallel import run_parallel
from shared import get_territories, require_active_membership, require_login, show_logged_in_as
from theme import empty_state

STEP = 30  # events shown at first and added by each "Load more"


def load_more(count):
    st.session_state["activity_shown"] = count + STEP


player_id = require_login()
show_logged_in_as()
membership_id, lobby_id, season_id = require_active_membership()
season = st.session_state.get("_validated_season")

page_header("Activity", st.session_state.get("current_lobby_name", ""))
activity_ui.load_styles()
activity_ui.view_switch("Feed")

try:
    entries, memberships, players = run_parallel(
        lambda: db.list_drink_entries(season_id),
        lambda: db.list_memberships_for_lobby(lobby_id, include_left=True),
        db.list_public_usernames)
    team_mode = st.session_state.get("current_lobby_mode") == "team" or any(e.team_id for e in entries)
    teams = db.list_lobby_teams(player_id, lobby_id) if team_mode else []
except (APIError, RequestError, RuntimeError, PermissionError):
    st.error("We couldn't load the activity. Reload the page to try again.")
    st.stop()

try:
    territory_names = {territory.id: territory.name for territory in get_territories()}
except (APIError, RequestError, RuntimeError):
    territory_names = {}  # rows then say "Unknown territory"; the feed itself still loads

now = current_time()
events = activity_events(entries)
try:
    launched_at = db.profile_medal_launch()
    if launched_at is not None and launched_at <= now and memberships:
        members_by_player = run_parallel(*(
            lambda pid=pid: db.list_memberships_for_player(pid, include_left=True)
            for pid in dict.fromkeys(member.player_id for member in memberships)
        ))
        all_members = [member for group in members_by_player for member in group]
        history = load_stat_history((member.lobby_id for member in all_members),
                                    known_entries={season_id: entries})
        events = with_promotions(events, lobby_promotions(lobby_id, all_members, history,
                                                           launched_at=launched_at, now=now))
except (APIError, RequestError, RuntimeError, PermissionError):
    st.warning("Medal promotions are temporarily unavailable.")
if not events:
    empty_state("activity", "list-bullets", "No activity yet",
                "The first drink of the season starts the feed.", check_in=True)
    st.stop()

usernames = {p["id"]: p["display_name"] for p in players}
member_names = {m.id: usernames.get(m.player_id, "Unknown player") for m in memberships}
team_names = {team.id: team.name for team in teams}
me_competitor = st.session_state.get("current_team_id") if team_mode else membership_id

shown = st.session_state.get("activity_shown", STEP)
st.markdown(activity_ui.feed_html(events[:shown], member_names=member_names, team_names=team_names,
                                  territory_names=territory_names, me_member=membership_id,
                                  me_competitor=me_competitor, season=season, now=now),
            unsafe_allow_html=True)
if len(events) > shown:
    st.button("Load more", key="activity_load_more", on_click=load_more, args=(shown,), width="stretch")
