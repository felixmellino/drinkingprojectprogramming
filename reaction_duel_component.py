"""Tap board for one player's three tries. PostgreSQL owns signals, results and points."""
from pathlib import Path
from streamlit.components.v1 import declare_component

_board = declare_component('reaction_duel', path=str(Path(__file__).parent / 'components' / 'reaction_duel'))


def reaction_board(run):
    from theme import component_tokens
    tokens = component_tokens()  # light, or light + dark when dark mode is on
    return _board(attempt=run, tokens=tokens, key=f"reaction_board_{run['id']}", default=None)
