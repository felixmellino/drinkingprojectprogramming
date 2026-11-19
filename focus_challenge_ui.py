"""Focus Challenge availability and saved full-screen attempts."""
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import uuid4

import streamlit as st
import data.db as db
from core.focus_challenge import component_action
from core.scoring_v1 import current_time, scoring_open
from focus_challenge_component import focus_board


def render_focus(player, season):
    # Import at call time to keep the shared service error policy in one place.
    from minigames_ui import SERVICE_ERRORS, _error
    try:
        info = db.focus_status(player, season.id)
    except (ValueError, PermissionError) + SERVICE_ERRORS as error:
        _error(error)
        return
    attempt = info.get('attempt')
    if attempt and (attempt['status'] == 'running'
                    or st.session_state.get('focus_start_request') == attempt['id']):
        # Recover a committed start whose reply was lost before the UI cleared it.
        st.session_state.pop('focus_start_request', None)
    if attempt and (attempt['status'] == 'running'
                    or st.session_state.get('focus_focused_id') == attempt['id']):
        st.session_state['focus_focused_id'] = attempt['id']
        with st.container(key='focus_stage'):
            value = focus_board(attempt)
            with st.container(key='focus_exit'):
                if st.button('Back to games', icon=':material/close:', key='focus_back',
                             help='Leave the screen. A running attempt keeps its deadline.'):
                    st.session_state.pop('focus_focused_id', None)
                    st.session_state.pop('minigame_selected', None)
                    st.rerun()
            action = component_action(value, attempt)
            if action and attempt['status'] == 'running':
                try:
                    db.focus_attempt_action(player, attempt['id'], attempt['revision'], *action)
                    st.rerun()
                except (ValueError, PermissionError) + SERVICE_ERRORS as error:
                    _error(error)
        return
    if st.button('All games', icon=':material/arrow_back:', key='focus_home'):
        st.session_state.pop('minigame_selected', None)
        st.rerun()
    st.subheader('Focus Challenge')
    st.write('Reaction → memory → precision. Pass all three in one attempt.')
    st.caption('A skill game for fun. Passing does not establish sobriety or fitness to ride or drive.')
    st.markdown('- **Reaction:** 5 trials, median ≤350 ms; no early taps.\n'
                '- **Memory:** repeat a fresh 7-position sequence.\n'
                '- **Precision:** 12 correct targets in 12 seconds; no wrong taps.')
    st.info('Win once per evening: ×1.5 on your ordinary season and territory check-ins for 60 minutes. '
            'Owner income uses boosted points. Chug Duel scoring stays unchanged.')
    st.caption('Your own Chug Duel entry counts toward unlocks. In teams, only your entries are boosted. '
               'Leaving or refreshing resumes the same attempt; its clock keeps running.')
    count, threshold = info['count'], info['threshold']
    st.progress(min(1.0, count / threshold), text=f'{count} accepted check-ins · next unlock at {threshold}')
    if info.get('boost_ends_at'):
        end = datetime.fromisoformat(info['boost_ends_at']).astimezone(ZoneInfo(season.timezone_name))
        st.success(f'Focus boost active · ×1.5 until {end:%H:%M:%S %Z}.')
    if info['won']:
        st.info('You have earned this evening’s boost. The evening resets at 06:00 in the lobby timezone.')
    elif attempt and attempt['status'] == 'failed':
        st.warning(f'Last attempt ended. The next attempt unlocks at {threshold} accepted check-ins.')
    if not scoring_open(current_time(), season):
        st.warning('Focus Challenge opens during this season’s scoring window.')
    allowed = (count >= threshold and not info['won'] and not info.get('boost_ends_at')
               and scoring_open(current_time(), season))
    if st.button('Start Focus Challenge', type='primary', width='stretch', disabled=not allowed):
        request = st.session_state.setdefault('focus_start_request', str(uuid4()))
        try:
            saved = db.start_focus_attempt(player, season.id, request)
            st.session_state['focus_focused_id'] = saved['id']
            st.session_state.pop('focus_start_request', None)
            st.rerun()
        except (ValueError, PermissionError) + SERVICE_ERRORS as error:
            _error(error)
