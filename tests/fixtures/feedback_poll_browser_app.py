"""Real Quiz Duel home with local data and one-second polling for popup QA."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import streamlit as st
import data.db as db
from core.models import Lobby, LobbyMembership
from quiz_duel_ui import render_quiz
from tests.test_scoring_v1 import START, season
from theme import apply_theme

st.set_page_config(page_title='WeGoPub · Polling feedback QA')
apply_theme()
st.caption('Local QA with synthetic data; no shared database or invitations.')
st.markdown(f"<style>{(ROOT / 'assets/minigames.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
db.get_client = lambda: (_ for _ in ()).throw(RuntimeError('Shared database disabled in feedback QA'))
db.quiz_status = lambda *_: dict(duels=[], available_points=2, outgoing=True, incoming=True, open=True)
db.invite_quiz_duel = lambda *_: (_ for _ in ()).throw(AssertionError('A blocked challenge must never send an invitation'))


@st.fragment(run_every='1s')
def live():
    st.session_state['qa_refreshes'] = st.session_state.get('qa_refreshes', 0) + 1
    render_quiz('pa', 'a', Lobby('lobby', 'Local QA', 'LOCAL'), season(),
                [LobbyMembership('a', 'pa', 'lobby', START), LobbyMembership('b', 'pb', 'lobby', START)],
                {'a': 'Alice', 'b': 'Bob'})
    st.caption(f"Automatic refreshes: {st.session_state['qa_refreshes']}")


live()
