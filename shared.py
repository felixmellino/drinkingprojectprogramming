"""Small helpers shared by the Streamlit pages. Lives at the project root
(not inside pages/) so Streamlit's multipage navigation doesn't list it as
its own page.

These functions only glue Streamlit + data/db.py + core/ together -- they
contain no game rules themselves.
"""

import streamlit as st

import data.db as db
from core.models import Player, Season, Territory
from data.territory_file import load_territories, territory_file_version
from account_ui import show_accounts, show_welcome
from device_login import sync_storage, set_identity, queue_storage
from postgrest.exceptions import APIError
from httpx import RequestError
from app_navigation import bottom_navigation, minigame_invite_badge
from theme import apply_theme
from lobby_selection import restore_selection
from season_recap_ui import banner as season_recap_banner
from parallel import run_parallel


def require_login() -> str:
    """Stop the page and prompt a login if nobody is logged in. Returns
    the logged-in player's id otherwise."""
    apply_theme()  # design system on every page, including the login screen
    st.session_state.pop("_validated_player", None)
    # Generic navigation has no private data. Handle a switch before repeating
    # this page's network reads; the destination always validates login afresh.
    navigation_rendered = "player_id" in st.session_state
    if navigation_rendered:
        bottom_navigation()
    token = sync_storage()
    if token is None and "player_id" not in st.session_state and not st.session_state.get("_remember_attempted"):
        st.info("Checking your saved sign-in…")
        st.stop()
    if token is not None and not st.session_state.get("_remember_attempted"):
        if token:
            try:
                player = db.get_remembered_player(token)
            except (APIError, RuntimeError, OSError, RequestError):
                st.error("Account service is unavailable. Please try again later.")
                st.stop()
            if player:
                set_identity(player)
                st.session_state["_device_token"] = token
                # The app was just opened on a remembered device: greet with the start screen first.
                if not st.session_state.get("start_seen") and "lobby_invite" not in st.query_params:
                    st.session_state["_show_welcome"] = True
            else:
                queue_storage("clear")
                st.rerun()
        st.session_state["_remember_attempted"] = True
    st.session_state.pop("_membership_prefetch", None)
    st.session_state.pop("_invite_badge_prefetch", None)
    if "player_id" in st.session_state:
        try:
            player = _get_player_and_prefetch_membership(st.session_state["player_id"])
        except (APIError, RuntimeError, OSError, RequestError):
            st.error("Account service is unavailable. Please try again later.")
            st.stop()
        if not player or not player.email or player.pin_hash != st.session_state.get("credential_version"):
            st.session_state.clear()
            st.session_state["_remember_attempted"] = True
            st.session_state["start_seen"] = True   # straight to the form, so "Please log in again" is visible
            queue_storage("clear")
            st.info("Please log in again.")
        else:
            st.session_state["_validated_player"] = player
    if "player_id" not in st.session_state:
        notice = st.session_state.pop("_profile_notice", None)
        if notice:
            st.session_state["start_seen"] = True   # a notice must not hide behind the start screen
            st.success(notice)
        show_accounts()
        st.stop()
    if st.session_state.get("_show_welcome"):
        show_welcome()   # one tap anywhere continues to the page that was opened
        st.stop()
    try:
        restore_selection(st.session_state["player_id"])
    except (APIError, RequestError, RuntimeError):
        st.warning("Your saved lobby could not be loaded. Retry by reopening a page, or choose a lobby on the Lobby page.")
    # Restored sessions did not have navigation at entry; render it once now.
    if not navigation_rendered:
        bottom_navigation()
    minigame_invite_badge()
    season_recap_banner()
    return st.session_state["player_id"]


MEMBERSHIP_PAGES = {"map", "standings", "minigames", "check_in", "check_in_photos", "activity"}


def _membership_key():
    keys = ("player_id", "current_membership_id", "current_lobby_id", "current_season_id")
    values = tuple(st.session_state.get(key) for key in keys)
    return values if all(values) else None


def _get_player_and_prefetch_membership(player_id):
    """Overlap fresh account, selected membership and invitation-count reads.

    The membership read only uses the ids already in this session and is used by
    require_active_membership only after the account check above has passed, so
    nothing is shown or trusted earlier than before. Any failure here is ignored:
    require_active_membership then simply asks again. The badge consumes its
    own fresh result once; later fragment ticks query again.
    """
    from app_navigation import current_page
    key = _membership_key()
    needs_context = key is not None and current_page() in MEMBERSHIP_PAGES
    season_id = st.session_state.get('current_season_id')

    def prefetch():
        try:
            return db.membership_context(*key)
        except (APIError, RequestError, RuntimeError, OSError):
            return None

    def badge():
        try:
            return db.pending_minigame_invite_count(player_id, season_id)
        except (APIError, RequestError, RuntimeError, OSError):
            return None  # No retry on this page load; the badge fragment retries later.

    calls = [lambda: db.get_player(player_id)]
    if needs_context:
        calls.append(prefetch)
    if season_id:
        calls.append(badge)
    results = iter(run_parallel(*calls))
    player = next(results)
    context = next(results) if needs_context else None
    if context is not None:
        st.session_state["_membership_prefetch"] = (key, context)
    if season_id:
        st.session_state['_invite_badge_prefetch'] = ((player_id, season_id), next(results))
    return player


def lobby_button(key: str = "open_lobbies") -> None:
    """Lobbies has no tab in the bottom bar: hints that send players there get a button."""
    if st.button("Open Lobbies", icon=":material/groups:", key=key):
        st.switch_page("pages/2_Lobby.py")


def require_active_membership() -> tuple[str, str, str]:
    """Stop the page with a message if no lobby is selected yet. Returns
    (membership_id, lobby_id, season_id) otherwise."""
    if "current_membership_id" not in st.session_state:
        st.info("Choose a lobby on the Lobby page to continue.")
        lobby_button()
        st.stop()
    st.session_state.pop("_validated_season", None)
    if not st.session_state.get("current_season_id"):
        st.info("Your selected lobby has no season ready. Open Lobbies, finish its setup with Retry lobby setup, or make another active lobby current.")
        lobby_button()
        st.stop()
    prefetched = st.session_state.pop("_membership_prefetch", None)
    try:
        if prefetched and prefetched[0] == _membership_key():
            selected, season = prefetched[1]  # read a moment ago, together with the account check
        else:
            selected, season = db.membership_context(st.session_state["player_id"],
                st.session_state["current_membership_id"], st.session_state.get("current_lobby_id"),
                st.session_state["current_season_id"])
    except (APIError, RequestError, RuntimeError):
        st.error("Lobby and season access could not be checked. Reopen Lobbies and try again.")
        lobby_button()
        st.stop()
    if selected is None:
        st.error("Your selected lobby membership is no longer available. Choose a lobby again.")
        lobby_button()
        st.stop()
    if season is None:
        st.error("This season does not belong to the selected lobby. Reopen Lobbies and make the intended lobby current again.")
        lobby_button()
        st.stop()
    st.session_state["current_team_id"] = selected.team_id
    st.session_state["_validated_season"] = season
    return (
        st.session_state["current_membership_id"],
        st.session_state["current_lobby_id"],
        st.session_state["current_season_id"],
    )


def authenticated_player() -> Player:
    """Reuse the fresh account read made by this page's require_login call."""
    player = st.session_state.get("_validated_player")
    if player is None or player.id != st.session_state.get("player_id"):
        raise RuntimeError("Please sign in again to load your profile.")
    return player


def selected_season(lobby_id: str, season_id: str) -> Season | None:
    """Reuse this page's validated season without a second database read."""
    season = st.session_state.get("_validated_season")
    if season and season.id == season_id and season.lobby_id == lobby_id:
        return season
    # Supports callers that establish their own membership context.
    return next((s for s in db.list_seasons_for_lobby(lobby_id) if s.id == season_id), None)


def get_territories() -> list[Territory]:
    """The game's territories, read from data/territories.geojson (R-T01).

    They are loaded and copied into the database once per version of the
    file (drink entries store a territory id that must exist there), then
    kept in memory. When the file changes, e.g. after a merge, the next page
    load picks up the new version by itself; no restart needed. If the
    database is unreachable the error is not cached and the next page load
    tries again."""
    return _load_and_sync(territory_file_version())


@st.cache_resource(show_spinner=False, max_entries=1)
def _load_and_sync(version: str) -> list[Territory]:
    # `version` is only the cache key: a new file version means a new load.
    territories = load_territories()
    db.upsert_territories(territories)
    return territories


def show_logged_in_as():
    """Kept for the pages that call it. It used to write "Logged in as" into the
    sidebar, which the app always hides; writing there made the sidebar flash
    open on every load, so it now shows nothing (the Profile button names you)."""
    return None
