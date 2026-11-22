"""The end-of-season story and awards card (R-S01 to R-S03).

Opened from a past lobby or after ending a test season early. Access is checked
again here: only players of that lobby, and only after the season ended.
"""
import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError

import data.db as db
import season_recap_ui as ui
from core.season_recap import build_recap
from drink_entry_ui import page_header
from parallel import run_parallel
from shared import get_territories, require_login, show_logged_in_as

LOAD_ERRORS = (APIError, RequestError, RuntimeError, OSError)

player_id = require_login()
show_logged_in_as()
lobby_name = st.session_state.get("_recap_lobby_name") or "Your lobby"
page_header("Season recap", lobby_name)


def back_to_lobby():
    if st.button("Open Lobby", key="season_recap_back"):
        st.switch_page("pages/2_Lobby.py")
    st.stop()


season_id = st.session_state.get("_recap_season_id")
if not season_id:
    st.info("Open a finished season from the Lobby page to see its awards.")
    back_to_lobby()
try:
    season, membership = db.recap_access(player_id, season_id)
except PermissionError:
    st.error("You can only see the awards of a season you played in.")
    back_to_lobby()
except ValueError:
    st.info("This season is still running. Its awards appear when it ends.")
    back_to_lobby()
except LOAD_ERRORS:
    st.error("We couldn't load the season. Reload the page to try again.")
    st.stop()

try:
    entries, transfers, memberships, players = run_parallel(
        lambda: db.list_drink_entries(season.id),
        lambda: db.list_season_transfers(season.id),
        lambda: db.list_memberships_for_lobby(season.lobby_id, include_left=True),
        db.list_public_usernames)
except LOAD_ERRORS:
    st.error("We couldn't load the season. Reload the page to try again.")
    st.stop()

players_by_id = {p["id"]: p["display_name"] for p in players}
names = {m.id: players_by_id.get(m.player_id, "Unknown player") for m in memberships}
me = membership.id
if membership.team_id or any(e.team_id for e in entries):
    try:
        names = {t.id: t.name for t in db.list_lobby_teams(player_id, season.lobby_id)}
    except (*LOAD_ERRORS, PermissionError):
        st.error("Teams could not be loaded. Reload the page to try again.")
        st.stop()
    me = membership.team_id
try:
    territory_names = {t.id: t.name for t in get_territories()}
except LOAD_ERRORS:
    territory_names = {}  # the takeover then says "a territory"

recap = build_recap(entries, transfers, me=me)
opened = st.session_state.setdefault("_recap_opened", "direct")
payload = ui.recap_payload(recap, names=names, territory_names=territory_names, me=me,
                           lobby_name=lobby_name, season=season)
value = ui.board(payload, animate=st.session_state.get("_recap_animate", False), opened=opened,
                 key=f"season_recap_board_{season.id}")

if recap.standings:
    st.download_button("Download standings (CSV)", ui.csv_text(recap, names),
                       file_name=f"{lobby_name} season standings.csv", mime="text/csv",
                       key="season_recap_csv", width="stretch")

if isinstance(value, dict) and value.get("action") == "close" and value.get("opened") == opened:
    try:
        db.finish_season_recap(player_id, season.id)
    except (PermissionError, ValueError):
        st.error("This season can't be finished from your account.")
        st.stop()
    except LOAD_ERRORS:
        st.error("We couldn't save that. Try Close again.")
        st.stop()
    ui.mark_seen(player_id, season.id)  # the lobby's pages open again (R-S03)
    for key in ("_recap_season_id", "_recap_animate", "_recap_opened"):
        st.session_state.pop(key, None)
    st.switch_page(st.session_state.pop("_recap_return", None) or "pages/2_Lobby.py")
