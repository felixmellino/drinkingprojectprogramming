"""Tap board for one player's three tries. PostgreSQL owns signals, results and points."""
from pathlib import Path
from streamlit.components.v1 import declare_component

_board = declare_component('reaction_duel', path=str(Path(__file__).parent / 'components' / 'reaction_duel'))


def reaction_board(run):
    css = (Path(__file__).parent / 'assets' / 'theme.css').read_text(encoding='utf-8')
    tokens = css[css.index(':root {'):css.index('/* Base */')]
    return _board(attempt=run, tokens=tokens, key=f"reaction_board_{run['id']}", default=None)
