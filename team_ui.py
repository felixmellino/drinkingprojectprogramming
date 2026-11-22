"""Team cards in a lobby dialog. Rules and atomic writes stay in core/data."""
from html import escape

import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError

import data.db as db
from action_feedback import action_button
from core.profile_photo import initials
from core.scoring_v1 import format_points
from core.leaderboard import season_leaderboard
from profile_picture_ui import avatar_html, member_pictures

ERRORS = (APIError, RequestError, RuntimeError, PermissionError, ValueError)


def avatar(name, photo=None):
    content = (f'<img src="data:image/jpeg;base64,{escape(photo, quote=True)}" alt="Team picture" style="width:64px;height:64px;border-radius:50%;object-fit:cover">'
               if photo else f'<span style="display:inline-grid;place-items:center;background:#d4e9de;color:#142B3D;border-radius:50%;width:64px;height:64px;font-size:24px">{escape(initials(name))}</span>')
    st.markdown(content, unsafe_allow_html=True)


def dismiss_lobby_dialog():
    st.session_state.pop('_lobby_dialog', None)
    st.session_state.pop('_opened_lobby_id', None)


@st.dialog("Lobby teams", width="large", on_dismiss=dismiss_lobby_dialog)
def open_team_lobby(player_id, lobby, season, *, finished=False):
    notice = st.session_state.pop('_team_notice', None) or st.session_state.pop('_lobby_notice', None)
    if notice:
        st.success(notice)
    try:
        teams = db.list_lobby_teams(player_id, lobby.id)
        members = db.list_memberships_for_lobby(lobby.id, include_left=True)
        me = next((m for m in members if m.player_id == player_id and m.left_at is None), None)
        names = {p['id']: p['display_name'] for p in db.list_public_usernames()}
        entries = db.list_drink_entries(season.id) if season else []
        transfers = db.list_season_transfers(season.id) if season else []
    except ERRORS:
        st.error('Teams could not be loaded. Close and reopen the lobby to try again.')
        return
    if me is None:
        dismiss_lobby_dialog()
        st.error('Your lobby membership is no longer available. Close this window and refresh your lobbies.')
        return
    st.text(lobby.name)
    st.code(lobby.invite_code, language=None)
    locked = any(e.membership_id == me.id for e in entries)
    totals = dict(season_leaderboard(entries, transfers))
    st.caption(f'{lobby.team_count} teams of up to {lobby.team_capacity} players. ' +
               ('Random assignment' if lobby.team_assignment == 'random' else 'Choose your team'))
    if not me.team_id:
        st.info('Join a team below before checking in. Your team locks after your first scored check-in.')
    elif locked:
        st.caption('Your team is locked because you have scored. Team members can still edit its name and picture.')
    # All members' pictures in one batch (A11: lobby members see each other's).
    pictures = member_pictures(player_id, members, [m.id for m in members]) if teams else {}
    for index, team in enumerate(teams):
        if index % 2 == 0:
            columns = st.columns(2)
        teammates = [m for m in members if m.team_id == team.id]
        own = me.team_id == team.id
        with columns[index % 2].container(border=True):
            avatar(team.name, team.photo_base64)
            if own:
                with st.popover(team.name, help='Edit your team name and picture'):
                    st.caption('Only members of this team can edit it.')
                    with st.form(f'edit_team_{team.id}'):
                        name = st.text_input('Team name', value=team.name, max_chars=40)
                        uploaded = st.file_uploader('Upload team picture', type=['jpg', 'jpeg', 'png', 'webp'], max_upload_size=10)
                        captured = st.camera_input('Take team picture')
                        remove = st.checkbox('Remove team picture')
                        saved = st.form_submit_button('Save team')
                    if saved:
                        try:
                            if remove and (captured or uploaded):
                                raise ValueError('Choose a new picture or remove the current one.')
                            picture = captured or uploaded
                            db.edit_lobby_team(player_id, team.id, name, picture.getvalue() if picture else None, remove_photo=remove)
                        except ERRORS as error:
                            st.error(str(error) if isinstance(error, ValueError) else 'The team could not be saved. Try again.')
                        else:
                            st.session_state['_team_notice'] = 'Team updated.'
                            st.rerun()
            else:
                st.text(team.name)
            st.caption(f'Team {team.number}: {len(teammates)}/{lobby.team_capacity} members, {format_points(totals.get(team.id, 0))} points' + (' (your team)' if own else ''))
            for member in teammates:
                label = names.get(member.player_id, 'Lobby member')
                suffix = ' (left, slot reserved)' if member.left_at else ''
                st.markdown(
                    '<div style="display:flex;align-items:center;gap:10px;margin:4px 0">'
                    + avatar_html(label, pictures.get(member.id), cls='team-member-avatar',
                                  style='display:inline-grid;place-items:center;flex:0 0 28px;width:28px;height:28px;'
                                        'border-radius:50%;background:var(--surface-raised);color:var(--text);'
                                        'font-size:11px;font-weight:700')
                    + f'<span style="overflow-wrap:anywhere">{escape(label + suffix)}</span></div>',
                    unsafe_allow_html=True)
            if not teammates:
                st.caption('No members yet')
            if lobby.team_assignment == 'manual' and not own:
                if action_button('Team full' if len(teammates) >= lobby.team_capacity else 'Join team', key=f'join_team_{team.id}',
                             inline=True, problems=[
                                 'This competition has ended. Create or join a new lobby to play on a team.' if finished else None,
                                 'Your team is locked after your first scored check-in. Continue with your current team; choose a different team in a new lobby.' if locked else None,
                                 f'This team is full ({lobby.team_capacity} players). Choose another team with a free place. Departed members keep their reserved places.' if len(teammates) >= lobby.team_capacity else None,
                             ]):
                    try:
                        db.choose_lobby_team(player_id, lobby.id, team.id)
                    except ERRORS as error:
                        st.error(str(error) if isinstance(error, ValueError) else 'Could not join this team. Try again.')
                    else:
                        st.session_state['_team_notice'] = 'Team joined.'
                        st.rerun()
    from lobby_ui import leave_lobby_controls, lobby_leaderboard, retry_setup, show_lobby_management
    if season is None:
        retry_setup(player_id, lobby)
    else:
        lobby_leaderboard(player_id, lobby, me, season)
    leave_lobby_controls(player_id, lobby)
    show_lobby_management(player_id, lobby, season, members)
    if st.button('Close', key='close_lobby_teams'):
        dismiss_lobby_dialog()
        st.rerun()
