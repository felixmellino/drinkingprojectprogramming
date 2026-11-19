"""Profile menu and forms. Validation and saved data live in core/data."""
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError
import data.db as db
from core.profile_stats import all_time_stats, season_finished
from core.scoring_v1 import format_points
from device_login import log_out, queue_storage, set_identity
from friends_ui import dismiss_friends, show_friends
from profile_picture_ui import show_picture_identity, show_picture_editor

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
        st.caption("Your account, friends and lifetime progress.")
        for key, label, icon in OPTIONS:
            if st.button(label, icon=icon, width="stretch", key=f"profile_{key}"):
                st.session_state["profile_view"] = key
                st.rerun()
        if st.button("Log out", icon=":material/logout:", width="stretch"):
            log_out()
        return
    if st.button("Back to Profile", icon=":material/arrow_back:"):
        dismiss_friends()
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
    show_photo_privacy(player.id)
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


def show_photo_privacy(player_id):
    st.subheader("Photo privacy")
    st.caption("Your saved check-in photos stay visible to you until deleted or expired. "
               "Teammates can see their team's photos. Other lobby members see yours only when sharing is on; "
               "in team lobbies, every current teammate must also switch sharing on.")
    try:
        enabled = db.get_photo_sharing(player_id, st.session_state["credential_version"])
        if st.session_state.pop("_photo_privacy_saved", False):
            st.success("Photo privacy saved.")
        with st.form("photo_privacy"):
            chosen = st.toggle("Share my check-in photos with other lobby players", value=enabled)
            st.caption("One setting for all lobbies, including past and future photos. "
                       "Turning it off blocks future access; photos already viewed or saved cannot be recalled. "
                       "Chug Duel copies follow each owner's setting independently.")
            submitted = st.form_submit_button("Save photo privacy", width="stretch")
        if submitted:
            db.save_photo_sharing(player_id, st.session_state["credential_version"], chosen)
            st.session_state["_photo_privacy_saved"] = True
            st.rerun()
    except SERVICE_ERRORS:
        st.error("We couldn't load or save photo privacy. Refresh to check your saved setting and try again.")


def show_stats(player_id):
    st.header("My stats")
    st.caption("All-time personal stats · Active and finished lobbies")
    memberships = db.list_memberships_for_player(player_id)
    now = datetime.now(timezone.utc)
    finished_season_ids = set()
    entries = []
    for member in memberships:
        seasons = db.list_seasons_for_lobby(member.lobby_id)
        for season in seasons:
            if season_finished(season, now):
                finished_season_ids.add(season.id)
            entries.extend(db.list_drink_entries(season.id))
    stats = all_time_stats(memberships, entries, finished_season_ids=finished_season_ids)
    css = (Path(__file__).parent / "assets" / "profile_stats.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    cards = [
        ("Total points", format_points(stats.points), "Your points across all lobbies"),
        ("Drinks", str(stats.drinks), "Accepted check-ins"),
        ("Lobbies played", str(stats.lobbies), "Lobbies you scored in"),
        ("Total Wins", str(stats.wins), "Completed season victories"),
    ]
    markup = '<section class="profile-stats" aria-label="All-time statistics from active and finished lobbies">'
    for label, value, detail in cards:
        markup += (f'<article class="profile-stat"><span>{escape(label)}</span>'
                   f'<strong>{escape(value)}</strong><small>{escape(detail)}</small></article>')
    st.markdown(markup + "</section>", unsafe_allow_html=True)
    st.caption("Your drink points plus personal territory-owner bonuses from individual lobbies. "
               "Team scores and team owner bonuses are excluded. Accepted check-ins count immediately; "
               "wins count only after a season ends.")
    if not stats.lobbies:
        st.info("No scored drinks yet. Your totals will appear here after your first accepted scoring check-in.")
