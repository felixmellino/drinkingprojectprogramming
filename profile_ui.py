"""Profile menu and forms. Validation and saved data live in core/data."""
from datetime import datetime, timezone
import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError
import data.db as db
from core.leaderboard import season_leaderboard
from core.scoring_v1 import utc
from core.territories import territory_owner
from device_login import log_out, queue_storage, set_identity
from friends_ui import show_friends
from profile_picture_ui import show_picture_identity, show_picture_editor
from shared import get_territories

SERVICE_ERRORS = (APIError, RequestError, RuntimeError, OSError)
OPTIONS = [
    ("edit", "Edit profile", ":material/edit:"),
    ("friends", "Friends", ":material/group:"),
    ("stats", "My stats", ":material/leaderboard:"),
    ("security", "Account & security", ":material/lock:"),
]


def show_profile(player):
    st.title("Profile")
    show_picture_identity(player.id, player.id, st.session_state.get("player_display_name", player.display_name))
    view = st.session_state.get("profile_view", "menu")
    if view == "menu":
        st.caption("Your account, friends and season progress.")
        for key, label, icon in OPTIONS:
            if st.button(label, icon=icon, width="stretch", key=f"profile_{key}"):
                st.session_state["profile_view"] = key
                st.rerun()
        if st.button("Log out", icon=":material/logout:", width="stretch"):
            log_out()
        return
    if st.button("Back to Profile", icon=":material/arrow_back:"):
        st.session_state["profile_view"] = "menu"
        st.rerun()
    try:
        if view == "edit":
            show_edit(player)
        elif view == "friends":
            show_friends(player.id)
        elif view == "stats":
            show_stats(player.id)
        elif view == "security":
            show_security(player)
    except ValueError as exc:
        st.error(str(exc))
    except APIError as exc:
        st.error("That username is already taken." if exc.code == "23505"
                 else "We couldn't save or load your details. Please try again.")
    except (RequestError, RuntimeError, OSError):
        st.error("We couldn't save or load your details. Please try again.")


def show_edit(player):
    st.header("Edit profile")
    st.caption("Only your username is public. Changing it keeps your friends and scores.")
    if st.session_state.pop("_profile_saved", False):
        st.success("Profile updated.")
    with st.form("edit_profile"):
        username = st.text_input("Username", value=player.display_name, max_chars=100)
        first = st.text_input("First name", value=player.first_name, max_chars=100)
        last = st.text_input("Surname", value=player.last_name, max_chars=100)
        submitted = st.form_submit_button("Save changes", width="stretch")
    if submitted:
        updated = db.update_profile(player.id, st.session_state["credential_version"], first, last, username)
        set_identity(updated)
        st.session_state["_profile_saved"] = True
        st.rerun()

    st.divider()
    show_picture_editor(player)


def show_security(player):
    st.header("Account & security")
    st.caption("These details are private. Email cannot be changed here.")
    st.text(f"Name: {player.first_name} {player.last_name}")
    st.text(f"Email: {player.email}")
    st.subheader("Change password")
    st.caption("Changing your password signs you out on every device. Log in again with your new password.")
    with st.form("change_password", clear_on_submit=True):
        current = st.text_input("Current password", type="password")
        password = st.text_input("New password", type="password", help="At least 8 characters")
        confirmation = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Change password", width="stretch")
    if submitted:
        db.update_password(player.id, st.session_state["credential_version"], current, password, confirmation)
        # Existing credential-version checks invalidate all old sessions.
        # Avoid a second database write that could fail after the save.
        st.session_state.clear()
        st.session_state["_remember_attempted"] = True
        queue_storage("clear")
        st.session_state["_profile_notice"] = "Password changed. Log in with your new password."
        st.rerun()


def show_stats(player_id):
    st.header("My stats")
    lobby_id = st.session_state.get("current_lobby_id")
    if not lobby_id:
        st.info("Choose a lobby on the Lobby page to see your stats.")
        return
    memberships = db.list_memberships_for_player(player_id)
    member = next((m for m in memberships if m.lobby_id == lobby_id), None)
    if not member:
        st.warning("You no longer belong to this lobby. Choose another on the Lobby page.")
        return
    now = datetime.now(timezone.utc)
    seasons = db.list_seasons_for_lobby(lobby_id)
    season = next((s for s in seasons if utc(s.starts_at) <= now < utc(s.ends_at)), None)
    st.caption(st.session_state.get("current_lobby_name", "Selected lobby"))
    if not season:
        st.info("This lobby has no current season. Open Lobby to start the next one.")
        return
    entries = db.list_drink_entries(season.id)
    ranking = season_leaderboard(entries)
    team_mode = st.session_state.get("current_lobby_mode") == "team" or getattr(member, "team_id", None) is not None
    identity = member.team_id if team_mode else member.id
    if team_mode:
        st.caption("Team stats · Combined points and territories for your team.")
        if not identity:
            st.info("Join a team from your lobby before checking in.")
            return
    rank = next((i for i, (mid, _) in enumerate(ranking, 1) if mid == identity), None)
    points = next((points for mid, points in ranking if mid == identity), 0)
    left, middle, right = st.columns(3)
    left.metric("Team season points" if team_mode else "Season points", str(points))
    middle.metric("Rank", f"#{rank}" if rank else "Unranked")
    try:
        owned = sum(territory_owner(entries, t.id) == identity for t in get_territories())
        right.metric("Territories owned", owned)
    except SERVICE_ERRORS:
        right.metric("Territories owned", "Unavailable")
        st.warning("Territory counts couldn't be loaded. Reopen My stats to retry.")
    st.caption("Current season only. Points and rank follow the same rules as Leaderboard.")
