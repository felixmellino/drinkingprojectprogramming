"""Time Duel invitations and saved two-phone gameplay."""
from uuid import uuid4
from datetime import datetime
import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError
import data.db as db
from action_feedback import action_button, explain
from core.action_feedback import duel_closed_message, opponent_message
from core.time_duel import ACTIVE, FINAL, component_action, validate_pair
from time_duel_component import time_board

SERVICE_ERRORS = (APIError, RequestError, RuntimeError, OSError, ValueError, PermissionError)


def _error(error, *, popup=False):
    show = explain if popup else st.error
    show(str(error) if isinstance(error, (ValueError, PermissionError, RuntimeError))
             else 'Time Duel is temporarily unavailable. Reopen it to recover your saved game.')


def _act(player, duel, action):
    try:
        saved = db.time_action(player, duel['id'], action)
        st.session_state.pop('time_accept_confirmation', None)
        if action == 'accept' and saved['status'] in ACTIVE:
            st.session_state['minigame_selected'] = 'time'
        st.rerun()
    except SERVICE_ERRORS as error:
        _error(error, popup=True)


def _render_invitations(player, member, state, labels):
    """Render invitations using their saved status."""
    pending = [d for d in state['duels'] if d['status'] == 'invited']
    incoming = [d for d in pending if d['opponent_id'] == member]
    confirmation = st.session_state.get('time_accept_confirmation')
    if confirmation not in {d['id'] for d in incoming}:
        st.session_state.pop('time_accept_confirmation', None)
    for duel in pending:
        with st.container(border=True, key='time_invite_' + duel['id']):
            if member == duel['challenger_id']:
                st.markdown('**Pending Challenge invite**')
                st.write('Time Duel: waiting for ' + labels.get(duel['opponent_id'], 'Lobby member'))
                if st.button('Cancel invitation', key='time_cancel_' + duel['id']):
                    _act(player, duel, 'cancel')
            else:
                st.markdown('**Time Duel invitation**')
                st.write(labels.get(duel['challenger_id'], 'Lobby member') + ' challenged you.')
                if len(incoming) > 1 and confirmation == duel['id']:
                    st.warning('If you accept this invite, the other invites for this minigame will be declined.')
                    if action_button('Confirm acceptance', key='time_confirm_' + duel['id'],
                                 type='primary', problems=["Your acceptance is used or reserved. Finish your current Time Duel, or wait for the next evening at 06:00 in the lobby timezone." if not state['incoming'] else None]):
                        _act(player, duel, 'accept')
                    if st.button('Keep invitations', key='time_keep_' + duel['id']):
                        st.session_state.pop('time_accept_confirmation', None)
                        st.rerun()
                elif action_button('Accept Time Duel', key='time_accept_' + duel['id'],
                               type='primary', problems=["Your acceptance is used or reserved. Finish your current Time Duel, or wait for the next evening at 06:00 in the lobby timezone." if not state['incoming'] else None]):
                    if len(incoming) > 1:
                        st.session_state['time_accept_confirmation'] = duel['id']
                        st.rerun()
                    else:
                        _act(player, duel, 'accept')
                if st.button('Decline', key='time_decline_' + duel['id']):
                    _act(player, duel, 'decline')
            # Compare server timestamps so a phone's clock cannot change expiry.
            remaining = max(0, int((datetime.fromisoformat(duel['expires_at']) -
                                   datetime.fromisoformat(duel['server_now'])).total_seconds()))
            st.caption(f'Expires in {remaining // 60}:{remaining % 60:02d}')
    return pending


def _result_card(duel, member, labels):
    """Shared minigame result card above the finished board (R-M10 reward)."""
    from minigames_ui import result_card
    other = duel['opponent_id'] if duel['challenger_id'] == member else duel['challenger_id']
    rival = labels.get(other, 'Opponent')
    if duel['status'] == 'draw':
        result_card('draw', '=', f'Same total error as {rival}',
                    note='Both get the ×1.25 boost only if every round counted.')
    elif duel.get('winner_id') == member:
        result_card('won', '×1.25', 'on your check-ins for the next hour', note=f'vs {rival}, 3 rounds')
    else:
        result_card('lost', '—', f'{rival} gets the ×1.25 boost', note='3 rounds, smallest total error wins')


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
        if focused['status'] in {'completed', 'draw'}:
            _result_card(focused, member, labels)
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
    st.caption('Three rounds with the same random 5–12 second target. Smallest total error wins. '
               'Fewer abandoned rounds wins first. Leaving or reloading a running timer loses that round.')
    st.info('Win ×1.25 personal season points on ordinary check-ins for one hour. '
            'Territory points and owner income stay unchanged. The highest active boost applies.')
    st.caption('Fairplay: no external clocks. A complete exact tie rewards both players.')
    st.caption('Test season with unlimited sequential duels' if state['test_mode'] else
               'One challenge and one acceptance per evening. Resets at 06:00 in ' + season.timezone_name)
    if state.get('boost_ends_at'):
        st.success('Your Time Duel boost is active. Check-in shows the applicable multiplier.')
    cols = st.columns(2)
    cols[0].caption('Challenge: ' + ('Available' if state['outgoing'] else 'Used / reserved'))
    cols[1].caption('Accept: ' + ('Available' if state['incoming'] else 'Used / reserved'))
    pending = _render_invitations(player, member, state, labels)
    own = next(m for m in members if m.id == member)
    opponents = []
    for other in members:
        try:
            validate_pair(own, other, lobby)
            opponents.append(other.id)
        except ValueError:
            continue
    if not state['open']:
        st.info(duel_closed_message(season))
    elif opponents:
        with st.form('time_invitation'):
            opponent = st.selectbox('Challenge player', opponents, format_func=lambda m: labels.get(m, 'Lobby member'))
            sent = st.form_submit_button('Send Time Duel challenge', type='primary')
        problems = [
            "You already have an open invitation. Cancel it above or wait for its answer before sending another." if any(d['challenger_id'] == member for d in pending) else None,
            "Your challenge is used or reserved. Finish your current Time Duel, or wait for the next evening at 06:00 in the lobby timezone." if not state['outgoing'] else None,
        ]
        if sent and any(problems):
            explain(problems)
            sent = False
        if sent:
            if st.session_state.get('time_invitation_target') != opponent:
                st.session_state.pop('time_invitation_id', None)
            st.session_state['time_invitation_target'] = opponent
            request = st.session_state.setdefault('time_invitation_id', str(uuid4()))
            try:
                db.invite_time_duel(player, season.id, request, opponent)
                st.session_state.pop('time_invitation_id', None)
                st.rerun()
            except SERVICE_ERRORS as error:
                _error(error, popup=True)
    else:
        st.info(opponent_message(own, lobby))
    with st.expander('Recent Time Duels'):
        for duel in (d for d in duels if d['status'] in FINAL):
            other = duel['opponent_id'] if duel['challenger_id'] == member else duel['challenger_id']
            verdict = ('Won' if duel.get('winner_id') == member else 'Lost') if duel.get('winner_id') else duel['status'].title()
            st.write(f"{verdict} vs {labels.get(other, 'Opponent')}")
            if st.button('View result', key='time_result_' + duel['id']):
                st.session_state['time_focused_id'] = duel['id']
                st.rerun(scope='fragment')
