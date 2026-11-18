"""Joined lobby cards. Existing ranking and picture access remain authoritative."""
import base64
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError

import data.db as db
from core.checkins import CheckinRejected
from core.leaderboard import season_leader
from core.lobby_overview import latest_season, lobby_status, time_left
from core.profile_photo import initials
from core.scoring_v1 import utc
from profile_picture_ui import PICTURE_ERRORS, load_picture

LOAD_ERRORS = (APIError, RequestError, RuntimeError)


def clear_selection():
    for key in ('current_membership_id', 'current_lobby_id', 'current_lobby_name', 'current_season_id', 'current_lobby_mode'):
        st.session_state.pop(key, None)


def select_lobby(lobby, membership, season):
    st.session_state.update(current_membership_id=membership.id,
                            current_lobby_id=lobby.id, current_lobby_name=lobby.name, current_lobby_mode=lobby.game_mode,
                            current_season_id=season.id if season else None)


def finish_label(season):
    return utc(season.ends_at).astimezone(ZoneInfo(season.timezone_name)).strftime('%d %b %Y, %H:%M %Z')


def card(lobby, season, status, now, leader_name=None, photo=None, ranking_available=True):
    name = escape(leader_name or 'No Leader')
    avatar = ''
    if status == 'active' and leader_name:
        picture = (f'<img src="data:image/jpeg;base64,{base64.b64encode(photo).decode("ascii")}" alt="Leader profile picture">'
                   if photo else escape(initials(leader_name)))
        avatar = f'<span class="lobby-avatar">{picture}</span>'
    label = 'Winner' if status == 'past' else 'Leader'
    result = (f'{label}: <strong>{name}</strong>' if leader_name else name) if ranking_available else 'Standings unavailable'
    meta = {'active': 'Running', 'past': 'Finished', 'setup': 'Setup incomplete', 'upcoming': 'Upcoming'}[status]
    if season and season.scoring_rules and season.scoring_rules.get('test_mode'):
        meta += ' · Test season (Wed 08:00–Sun 18:00)'
    if lobby.game_mode == 'team':
        meta += f' · Team mode · {lobby.team_count} × {lobby.team_capacity}'
    timing = (f'Finished {finish_label(season)}' if status == 'past' else
              f'{time_left(season.ends_at, now)} left · Ends {finish_label(season)}' if status == 'active' else
              'Competition has not started yet' if status == 'upcoming' else 'No competition dates yet')
    st.markdown(f'<article class="lobby-card lobby-{status}"><p class="lobby-meta">{meta}</p>'
                f'<h3>{escape(lobby.name)}</h3><div class="lobby-person">{avatar}<span>{result}</span></div>'
                f'<p class="lobby-countdown">{escape(timing)}</p></article>', unsafe_allow_html=True)


@st.fragment(run_every='60s')
def show_lobbies(player_id, memberships):
    css = (Path(__file__).parent / 'assets/lobbies.css').read_text()
    st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)
    notice = st.session_state.pop('_lobby_notice', None)
    if notice:
        st.success(notice)
    st.button('Refresh lobbies')
    # Timed refreshes must not retain access after a membership is removed.
    try:
        memberships = db.list_memberships_for_player(player_id)
    except LOAD_ERRORS:
        st.error('Your lobby access could not be checked. Use Refresh lobbies to try again.')
        return
    if not memberships:
        clear_selection()
        st.info('You have not joined any lobbies yet. Create one or join with a code below.')
        return
    try:
        lobbies = {l.id: l for l in db.list_lobbies()}
    except LOAD_ERRORS:
        st.error('Your lobbies could not be loaded. Use Refresh lobbies to try again.')
        return
    now = datetime.now(timezone.utc)
    groups = {key: [] for key in ('active', 'past', 'upcoming', 'setup')}
    for membership in memberships:
        lobby = lobbies.get(membership.lobby_id)
        if lobby is None:
            continue
        try:
            season = latest_season(db.list_seasons_for_lobby(lobby.id))
        except LOAD_ERRORS:
            st.warning(f'Dates for {lobby.name} are unavailable. Use Refresh lobbies to try again.')
            continue
        groups[lobby_status(season, now)].append((lobby, membership, season))
    for status in ('active', 'past', 'upcoming'):
        groups[status].sort(key=lambda row: (utc(row[2].ends_at if status == 'past' else row[2].starts_at), row[0].id), reverse=True)
    # Re-evaluate on every refresh, including the exact finish boundary.
    # Opening another card navigates immediately, so it stays selected there.
    if groups['active']:
        select_lobby(*groups['active'][0])
        st.caption(f'Automatically selected: {groups["active"][0][0].name}')
    else:
        clear_selection()
    for status, heading in (('active', 'Active Lobbies'), ('past', 'Past Lobbies'),
                            ('upcoming', 'Upcoming Lobbies'), ('setup', 'Incomplete setup')):
        rows = groups[status]
        if not rows and status not in ('active', 'past'):
            continue
        st.subheader(heading)
        if not rows:
            st.caption('No active lobbies.' if status == 'active' else 'No past lobbies yet.')
        for lobby, membership, season in rows:
            leader_name, photo, available = None, None, True
            if season:
                try:
                    leader = season_leader(db.list_drink_entries(season.id))
                    if leader:
                        if lobby.game_mode == 'team':
                            teams = db.list_lobby_teams(player_id, lobby.id)
                            winning = next((t for t in teams if t.id == leader), None)
                            leader_name = winning.name if winning else 'Team'
                            photo = base64.b64decode(winning.photo_base64) if winning and winning.photo_base64 else None
                        else:
                            leader_name = db.membership_display_name(leader, lobby.id)
                        if status == 'active' and lobby.game_mode == 'individual':
                            members = db.list_memberships_for_lobby(lobby.id)
                            owner = next((m.player_id for m in members if m.id == leader), None)
                            if owner:
                                try:
                                    photo = load_picture(player_id, owner)
                                except PICTURE_ERRORS:
                                    pass
                except LOAD_ERRORS:
                    available = False
            card(lobby, season, status, now, leader_name, photo, available)
            if status in ('active', 'past'):
                if st.button('View results' if status == 'past' else 'Open lobby', key=f'open_lobby_{lobby.id}', width='stretch'):
                    select_lobby(lobby, membership, season)
                    if lobby.game_mode == 'team':
                        st.session_state["_lobby_dialog"] = lobby.id
                    else:
                        st.switch_page('pages/4_Standings.py')
            if st.session_state.get('_lobby_dialog') == lobby.id and status in ('active', 'past'):
                from team_ui import open_team_lobby
                select_lobby(lobby, membership, season)
                open_team_lobby(player_id, lobby, season, finished=status == 'past')
            if status == 'setup':
                with st.expander('Retry lobby setup'):
                    with st.form(f'retry_setup_{lobby.id}'):
                        duration = st.radio('Lobby duration', ['1_week', '1_month', '3_months'],
                                            format_func=lambda value: value.replace('_', ' '), horizontal=True)
                        zone = st.text_input('Lobby timezone', value='Europe/Lisbon')
                        test_mode = st.checkbox('Test season: Wednesday 08:00–Sunday 18:00',
                                                key=f'retry_test_season_{lobby.id}')
                        retry = st.form_submit_button('Start lobby')
                    if retry:
                        try:
                            db.start_scoring_season(player_id, lobby.id, duration, zone,
                                                    **({'test_mode': True} if test_mode else {}))
                        except (PermissionError, CheckinRejected, *LOAD_ERRORS):
                            st.error('Lobby setup failed. Check the timezone and database setup, then refresh.')
                        else:
                            st.rerun()
