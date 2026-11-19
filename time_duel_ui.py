"""Time Duel invitations and saved two-phone gameplay."""
from uuid import uuid4
import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError
import data.db as db
from core.time_duel import ACTIVE, FINAL, component_action, validate_pair
from time_duel_component import time_board

SERVICE_ERRORS = (APIError, RequestError, RuntimeError, OSError, ValueError, PermissionError)


def _error(error):
    st.error(str(error) if isinstance(error, (ValueError, PermissionError, RuntimeError))
             else 'Time Duel is temporarily unavailable. Reopen it to recover your saved game.')


def _act(player, duel, action):
    try:
        db.time_action(player, duel['id'], action)
        st.rerun(scope='fragment')
    except SERVICE_ERRORS as error:
        _error(error)


def render_time(player, member, lobby, season, members, labels):
    try:
        state = db.time_status(player, season.id)
    except SERVICE_ERRORS as error:
        _error(error)
        if st.button('All games', key='time_error_back'):
            st.session_state.pop('minigame_selected', None)
            st.rerun()
        return
    duels = state['duels']
    focused = next((d for d in duels if d['status'] in ACTIVE), None) or next(
        (d for d in duels if d['id'] == st.session_state.get('time_focused_id')), None)
    if focused:
        st.session_state['time_focused_id'] = focused['id']
        ack = 'time_ack_' + focused['id']
        with st.container(key='time_stage'):
            value = time_board(focused, member, labels, st.session_state.get(ack))
            parsed = component_action(value, focused)
            if parsed and value['event_id'] != st.session_state.get(ack):
                action, round_no, ms = parsed
                if action == 'back' and focused['status'] in FINAL:
                    st.session_state[ack] = value['event_id']
                    st.session_state.pop('time_focused_id', None)
                    st.rerun(scope='fragment')
                elif action != 'back':
                    try:
                        db.time_action(player, focused['id'], action, round_no, ms)
                        st.session_state[ack] = value['event_id']
                        st.rerun(scope='fragment')
                    except SERVICE_ERRORS as error:
                        _error(error)
        return
    if st.button('All games', key='time_back'):
        st.session_state.pop('minigame_selected', None)
        st.rerun()
    st.subheader('Time Duel', anchor=False)
    st.write('Feel the seconds. Tap to start, then stop without seeing a clock.')
    st.caption('Three rounds · Same random 5–12 second target · Smallest total error wins. '
               'Fewer abandoned rounds wins first. Leaving or reloading a running timer loses that round.')
    st.info('Win ×1.25 personal season points on ordinary check-ins for one hour. '
            'Territory points and owner income stay unchanged. The highest active boost applies.')
    st.caption('Fairplay: no external clocks. A complete exact tie rewards both players.')
    st.caption('Test season · Unlimited sequential duels' if state['test_mode'] else
               'One challenge + one acceptance per evening · Resets at 06:00 in ' + season.timezone_name)
    if state.get('boost_ends_at'):
        st.success('Your Time Duel boost is active. Check-in shows the applicable multiplier.')
    cols = st.columns(2)
    cols[0].caption('Challenge: ' + ('Available' if state['outgoing'] else 'Used / reserved'))
    cols[1].caption('Accept: ' + ('Available' if state['incoming'] else 'Used / reserved'))
    pending = [d for d in duels if d['status'] == 'invited']
    for duel in pending:
        with st.container(border=True):
            st.write(f"{labels.get(duel['challenger_id'], 'Player')} vs {labels.get(duel['opponent_id'], 'Player')}")
            if member == duel['opponent_id']:
                if st.button('Accept Time Duel', key='time_accept_' + duel['id'], type='primary', disabled=not state['incoming']):
                    _act(player, duel, 'accept')
                if st.button('Decline', key='time_decline_' + duel['id']):
                    _act(player, duel, 'decline')
            elif st.button('Cancel invitation', key='time_cancel_' + duel['id']):
                _act(player, duel, 'cancel')
    own = next(m for m in members if m.id == member)
    opponents = []
    for other in members:
        try:
            validate_pair(own, other, lobby)
            opponents.append(other.id)
        except ValueError:
            continue
    if not state['open']:
        st.info('Time Duel opens during the scoring window. Test seasons can play throughout an active season.')
    elif opponents:
        with st.form('time_invitation'):
            opponent = st.selectbox('Challenge player', opponents, format_func=lambda m: labels.get(m, 'Lobby member'))
            sent = st.form_submit_button('Send Time Duel challenge', type='primary',
                disabled=not state['outgoing'] or any(d['challenger_id'] == member for d in pending))
        if sent:
            request = st.session_state.setdefault('time_invitation_id', str(uuid4()))
            try:
                db.invite_time_duel(player, season.id, request, opponent)
                st.session_state.pop('time_invitation_id', None)
                st.rerun(scope='fragment')
            except SERVICE_ERRORS as error:
                _error(error)
    else:
        st.info('Another eligible lobby member is needed; team lobbies require an opposing team.')
    with st.expander('Recent Time Duels'):
        for duel in (d for d in duels if d['status'] in FINAL):
            st.write(labels.get(duel.get('winner_id'), duel['status'].title()))
            if st.button('View result', key='time_result_' + duel['id']):
                st.session_state['time_focused_id'] = duel['id']
                st.rerun(scope='fragment')
