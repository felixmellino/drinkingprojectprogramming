"""Local visual fixture for all duel lobbies; no network or real accounts."""
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import streamlit as st
import data.db as db
import minigames_ui as ui
from app_navigation import bottom_navigation
from core.models import Lobby, LobbyMembership
from tests.test_scoring_v1 import START, season

st.set_page_config(page_title="Minigames · local preview", layout="centered")
dark = st.query_params.get("dark") == "1"
st.session_state["wego_dark_mode"] = dark
css = (ROOT / "assets/theme.css").read_text(encoding="utf-8")
if dark:
    css += (ROOT / "assets/theme_dark.css").read_text(encoding="utf-8")
st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

members = [LobbyMembership("a", "pa", "lobby", START), LobbyMembership("b", "pb", "lobby", START)]
labels = {"a": "Alex", "b": "Jamie"}
game = season()
lobby = Lobby("lobby", "Local preview", "LOCAL")
ui.current_time = lambda: START
ui.track_location = lambda: None
db.list_memberships_for_lobby = lambda _: members
db.list_public_usernames = lambda: [dict(id=m.player_id, display_name=labels[m.id]) for m in members]
db.pending_minigame_invites = lambda *_: {}

state = dict(duels=[], available_points=20, outgoing=True, incoming=True, open=True,
             test_mode=False, boost_ends_at=None)
db.list_chug_duels = lambda *_: []
db.quiz_status = db.time_status = db.reaction_status = lambda *_: deepcopy(state)

def preview_invite(*args):
    st.session_state["preview_invite"] = list(args[3:])

db.invite_chug_duel = db.invite_quiz_duel = db.invite_time_duel = db.invite_reaction_duel = preview_invite
st.session_state.setdefault("minigame_selected", st.query_params.get("game", "chug_duel"))
bottom_navigation("minigames")
ui.render_minigames("pa", "a", lobby, game)
