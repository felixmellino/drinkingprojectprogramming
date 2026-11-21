"""Create/join dialogs; the existing lobby and scoring rules stay in core/data."""
from datetime import datetime, timezone
from zoneinfo import available_timezones

import streamlit as st

import data.db as db
from core.checkins import CheckinRejected
from core.action_feedback import checkin_message
from core.lobbies import create_lobby, join_lobby
from core.lobby_overview import latest_season, lobby_status
from httpx import RequestError
from postgrest.exceptions import APIError


def dismiss_dialog():
    st.session_state.pop('_lobby_dialog', None)


def open_joined_lobby(lobby_id, message, *, make_current):
    dismiss_dialog()
    st.session_state['_opened_lobby_id'] = lobby_id
    if make_current:
        st.session_state['_lobby_choice_pending'] = lobby_id
    st.session_state['_lobby_notice'] = message
    st.rerun()


@st.dialog('Create a lobby', dismissible=True, on_dismiss=dismiss_dialog)
def create_dialog(player_id):
    st.info('Creating a lobby will make it your current lobby once its season starts.')
    zones = sorted(available_timezones())
    mode = st.radio("Competition mode", ["individual", "team"], format_func=str.title, horizontal=True,
                    key='pill_radio_competition_mode')
    count = capacity = assignment = None
    if mode == "team":
        count = st.number_input("Number of teams", min_value=2, max_value=16, value=2)
        capacity = st.number_input("Players per team", min_value=1, max_value=20, value=2)
        assignment = st.radio("Team assignment", ["manual", "random"],
                              format_func=lambda value: "Players choose" if value == "manual" else "Random", horizontal=True)
        st.caption("Teams start as Team 1, Team 2, etc. Members can edit their team's name and picture. Team totals decide the leaderboard and territory ownership.")
    with st.form("create_lobby_form"):
        lobby_name = st.text_input("Lobby name").strip()
        length_choice = st.radio("Lobby duration", options=["1_week", "1_month", "3_months"],
                                 format_func=lambda value: value.replace("_", " "), horizontal=True)
        timezone_name = st.selectbox("Lobby timezone", zones, index=zones.index("Europe/Lisbon"))
        test_mode = st.checkbox("Test season: Wednesday 08:00–Sunday 18:00", key="create_test_season",
                                help="For QA lobbies only. The selected rules stay fixed for this season.")
        st.caption("Normal scoring: Thu 18:00–Sun 18:00. Test scoring: Wed 08:00–Sun 18:00. Both use the lobby timezone. When the duration ends, this lobby closes permanently.")
        create_submitted = st.form_submit_button("Create lobby")

    if st.button('Cancel', key='cancel_create_lobby'):
        dismiss_dialog()
        st.rerun()

    if create_submitted:
        if not lobby_name:
            st.error("Lobby name is required.")
        else:
            try:
                lobby = create_lobby(lobby_name, mode, team_count=count, team_capacity=capacity, team_assignment=assignment)
                db.insert_lobby(lobby)
                membership = join_lobby(player_id, lobby.invite_code, [lobby], [])
                db.insert_membership(membership)
            except ValueError as error:
                st.error(str(error))
                return
            except (APIError, RequestError, RuntimeError):
                st.error(f"Could not confirm lobby creation. Refresh your lobbies before creating another. If the lobby was created but is missing from your list, try Join with a code using {lobby.invite_code}.")
                return
            try:
                db.start_scoring_season(player_id, lobby.id, length_choice, timezone_name,
                                                 **({"test_mode": True} if test_mode else {}))
            except CheckinRejected as error:
                open_joined_lobby(lobby.id, f"Lobby created. {checkin_message(error.reason)} Use Retry lobby setup below if needed.",
                                  make_current=False)
            except PermissionError:
                open_joined_lobby(lobby.id, "Lobby created, but your membership could not be confirmed for season setup. Close this window, refresh Lobbies, reopen this lobby and use Retry lobby setup.",
                                  make_current=False)
            except (APIError, RequestError, RuntimeError):
                open_joined_lobby(lobby.id, "Lobby created. Its season setup could not be confirmed. Reopen this lobby and check its season before using Retry lobby setup.",
                                  make_current=False)

            open_joined_lobby(lobby.id, f"Lobby created! Invite code: {lobby.invite_code}", make_current=True)


@st.dialog('Join with a code', dismissible=True, on_dismiss=dismiss_dialog)
def join_dialog(player_id):
    st.info('Joining will make this your current lobby. Finished lobbies are available for viewing.')
    with st.form("join_lobby_form"):
        invite_code = st.text_input("Invite code").strip().upper()
        join_submitted = st.form_submit_button("Join lobby")

    if st.button('Cancel', key='cancel_join_lobby'):
        dismiss_dialog()
        st.rerun()

    if join_submitted:
        try:
            memberships = db.list_memberships_for_player(player_id, include_left=True)
            lobbies = db.list_lobbies()
            membership = join_lobby(player_id, invite_code, lobbies, memberships)
        except (APIError, RequestError, RuntimeError):
            st.error("Could not load lobbies. Please try again.")
        except ValueError:
            st.error("That invite code doesn't match any lobby. Check the code with the person who invited you and enter it again.")
        else:
            is_new = membership.id not in {m.id for m in memberships}
            lobby = next(l for l in lobbies if l.id == membership.lobby_id)
            try:
                season = latest_season(db.list_seasons_for_lobby(lobby.id))
                if is_new:
                    db.insert_membership(membership)
                elif membership.left_at is not None:
                    db.rejoin_lobby(player_id, membership.lobby_id)
            except (PermissionError, ValueError) as error:
                st.error(str(error))
                return
            except (APIError, RequestError, RuntimeError):
                st.error("Could not finish joining the lobby. Refresh your lobbies before trying again.")
                return

            open_joined_lobby(lobby.id, f"Joined {lobby.name}!",
                              make_current=lobby_status(season, datetime.now(timezone.utc)) != 'past')
