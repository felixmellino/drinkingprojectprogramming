"""Selected lobby activity, including lifetime medal promotions earned there."""

import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError

import activity_ui
import data.db as db
from core.activity import activity_events, with_promotions
from core.medals import lobby_promotions
from data.profile_history import load_stat_history
from core.scoring_v1 import current_time, utc
from drink_entry_ui import page_header
from parallel import run_parallel
from profile_picture_ui import member_pictures, picture_access
from shared import get_territories, require_active_membership, require_login, show_logged_in_as
from theme import empty_state

STEP = 30  # events shown at first and added by each "Load more"
PROMOTIONS_REUSE_SECONDS = 300


def load_more(count):
    st.session_state["activity_shown"] = count + STEP


def duel_data():
    """Stake transfers and finished duels; None if unavailable (the feed still loads)."""
    try:
        return run_parallel(lambda: db.list_season_transfers(season_id),
                            lambda: db.list_duel_results(season_id))
    except (APIError, RequestError, RuntimeError, OSError):
        return None


def medal_launch():
    try:
        return db.profile_medal_launch(), False
    except (APIError, RequestError, RuntimeError, OSError):
        return None, True


player_id = require_login()
show_logged_in_as()
membership_id, lobby_id, season_id = require_active_membership()
season = st.session_state.get("_validated_season")
scope = (player_id, lobby_id, season_id)
if st.session_state.get("activity_scope") != scope:
    st.session_state["activity_scope"] = scope
    st.session_state["activity_shown"] = STEP

page_header("Activity", st.session_state.get("current_lobby_name", ""))
activity_ui.load_styles()
activity_ui.view_switch("Feed")

try:
    entries, memberships, players, (launched_at, medals_unavailable), duels, access = run_parallel(
        lambda: db.list_drink_entries(season_id),
        lambda: db.list_memberships_for_lobby(lobby_id, include_left=True),
        db.list_public_usernames, medal_launch, duel_data, lambda: picture_access(player_id))
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
transfers, duel_results = duels if duels is not None else ((), None)
events = activity_events(entries, transfers, duel_results)


def promotions():
    """Medal promotions need every member's lifetime history, which is many reads.
    Reuse the result for this visit while the lobby's check-ins and members are
    unchanged, and at most PROMOTIONS_REUSE_SECONDS, so Load more and other
    reruns don't reload all of it. A finished season can add a win, so that
    state is part of the key too."""
    key = (lobby_id, season_id, launched_at, len(entries), entries[-1].id if entries else None,
           len(memberships), season is not None and utc(now) >= utc(season.ends_at))
    saved = st.session_state.get("_activity_promotions")
    if saved and saved[0] == key and (now - saved[1]).total_seconds() < PROMOTIONS_REUSE_SECONDS:
        return saved[2]
    all_members = db.list_membership_history_for_players(member.player_id for member in memberships)
    history = load_stat_history((member.lobby_id for member in all_members), known_entries={season_id: entries})
    result = lobby_promotions(lobby_id, all_members, history, launched_at=launched_at, now=now)
    st.session_state["_activity_promotions"] = (key, now, result)
    return result


try:
    if launched_at is not None and launched_at <= now and memberships:
        events = with_promotions(events, promotions())
except (APIError, RequestError, RuntimeError, OSError):
    medals_unavailable = True
if medals_unavailable:
    st.warning("Medal promotions are temporarily unavailable.")
if duels is None:
    st.warning("Quiz, Reaction and Time Duel results are temporarily unavailable.")
if not events:
    empty_state("activity", "list-bullets", "No activity yet",
                "The first drink of the season starts the feed.", check_in=True)
    st.stop()

usernames = {p["id"]: p["display_name"] for p in players}
member_names = {m.id: usernames.get(m.player_id, "Unknown player") for m in memberships}
team_names = {team.id: team.name for team in teams}
me_competitor = st.session_state.get("current_team_id") if team_mode else membership_id

shown = st.session_state.get("activity_shown", STEP)
# Pictures only for the players in the rows shown (A11: lobby members see each other's).
pictures = member_pictures(player_id, memberships, {event.member for event in events[:shown]}, access)
st.markdown(activity_ui.feed_html(events[:shown], member_names=member_names, team_names=team_names,
                                  territory_names=territory_names, me_member=membership_id,
                                  me_competitor=me_competitor, season=season, now=now, pictures=pictures),
            unsafe_allow_html=True)
if len(events) > shown:
    st.button("Load more", key="activity_load_more", on_click=load_more, args=(shown,), width="stretch")
