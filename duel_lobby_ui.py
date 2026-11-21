"""Shared presentation for duel lobbies; game rules and actions stay in each game."""
from contextlib import contextmanager
from html import escape

import streamlit as st

from theme import button_icons, icon_url


GAMES = {
    "chug": dict(title="Chug Duel", icon="beer-stein", line="One phone. Two players. One winner.",
                 tags=("1 vs 1", "Shared phone"),
                 steps=(("Pair up", "Choose a player, drink and size. They accept on their phone."),
                        ("Get ready", "Take one photo of both drinks. Both tap Ready on your phone."),
                        ("Race", "Wait for GO. The first finish tap wins both drinks’ base points."))),
    "reaction": dict(title="Reaction Duel", icon="game-controller", line="Wait for it. Make your move.",
                     tags=("1 vs 1", "Best of 3"),
                     steps=(("Challenge", "Choose a player and stake. You each play on your own phone."),
                            ("React", "Wait for TAP NOW, then tap. Too early? That try restarts."),
                            ("Win", "The faster reaction wins each round. Win the duel to take the stake."))),
    "quiz": dict(title="Quiz Duel", icon="brain", line="Quick thinking. Friendly rivalry.",
                 tags=("1 vs 1", "3 rounds + tiebreaks"),
                 steps=(("Challenge", "Choose a player and stake. Both tap Ready on their own phone."),
                        ("Answer", "Knowledge, multiplication, then logic. The faster correct answer wins each round."),
                        ("Win", "Most rounds wins the stake. A tie goes to deciding questions."))),
    "time": dict(title="Time Duel", icon="arrow-clockwise", line="Feel the seconds. Trust your timing.",
                 tags=("1 vs 1", "3 rounds"),
                 steps=(("Get ready", "Challenge a player. Both tap Ready to reveal the same target."),
                        ("Feel the time", "Tap Start, then Stop when the target time feels right. The clock stays hidden."),
                        ("Win", "The smallest total error wins a ×1.25 check-in boost for one hour."))),
}


def game_header(title, line, back_key):
    """The same navigation and compact, lightly playful heading on every game."""
    button_icons({back_key: "caret-left"})
    with st.container(key="duel_back_" + back_key):
        if st.button("All games", key=back_key, type="tertiary"):
            st.session_state.pop("minigame_selected", None)
            st.rerun()
    game = next((g for g in GAMES.values() if g["title"] == title), None)
    icon = f'<i style="mask:url({icon_url(game["icon"])}) center/contain no-repeat" aria-hidden="true"></i>' if game else ""
    subtitle = line or (game["line"] if game else "")
    tags = "".join(f'<span>{escape(tag)}</span>' for tag in game["tags"]) if game else ""
    st.markdown(
        f'<header class="duel-heading"><div><h1 class="game-title">{escape(title)}</h1>'
        f'<p class="game-line">{escape(subtitle)}</p></div><div class="duel-emblem">{icon}</div></header>'
        f'<div class="duel-tags">{tags}</div>', unsafe_allow_html=True)


@contextmanager
def game_setup(game, *, detail=""):
    """One card for the options and the primary action, always above the guide."""
    with st.container(key="duel_setup_" + game, border=True):
        extra = f'<span>{escape(detail)}</span>' if detail else ""
        st.markdown(f'<div class="duel-setup-heading"><strong>Your challenge</strong>{extra}</div>',
                    unsafe_allow_html=True)
        yield


def game_guide(game, *, rules=""):
    steps = "".join(
        f'<li><span class="duel-step">{number}</span><div><strong>{escape(title)}</strong>'
        f'<span>{escape(text)}</span></div></li>'
        for number, (title, text) in enumerate(GAMES[game]["steps"], 1))
    st.markdown(f'<section class="duel-guide" aria-label="How to play"><h2>How to play</h2>'
                f'<ol>{steps}</ol></section>', unsafe_allow_html=True)
    if rules:
        with st.expander("Rules & limits"):
            st.markdown(rules)


@contextmanager
def recent_matches(game, matches):
    """Always available, even before the player's first match."""
    with st.container(key="duel_history_" + game):
        with st.expander("Recent matches", icon=":material/history:"):
            if not matches:
                st.markdown('<p class="duel-history-empty">No matches yet. Your duels will appear here.</p>',
                            unsafe_allow_html=True)
            yield
