"""Read-only leaderboard presentation. Ranking comes from the core helpers."""

from __future__ import annotations

from decimal import Decimal
from html import escape
from pathlib import Path

import streamlit as st

from core.profile_photo import initials
from core.scoring_v1 import format_points
from photo_history_ui import identity_colour


def load_styles() -> None:
    css = (Path(__file__).parent / "assets" / "standings.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def reached_first(rows, index: int) -> bool:
    """True when the row below has the same points: this row ranks higher only
    because it reached the score first."""
    return index + 1 < len(rows) and Decimal(str(rows[index][1])) == Decimal(str(rows[index + 1][1]))


def _tie_tag(rows, index: int) -> str:
    return '<span class="ranks-first">reached first</span>' if reached_first(rows, index) else ""


def leaderboard(rows, names: dict, current_member: str, *, team_mode: bool = False) -> None:
    """One clean ranked list, in exactly the order returned by season_leaderboard."""
    you_label = "Your team" if team_mode else "You"
    markup = '<ol class="ranks-list" aria-label="Season ranking">'
    for index, (member, points) in enumerate(rows):
        rank = index + 1
        name = names.get(member, "Unknown player")
        you = member == current_member
        # Same hashed per-player colour as their photo-history frames,
        # so a face recurring across pages reads as the same identity.
        identity = {"team_id": member} if team_mode else {"membership_id": member}
        tag = f'<span class="ranks-you">{you_label}</span>' if you else ""
        markup += (
            f'<li class="ranks-row{" ranks-row-you" if you else ""}">'
            f'<span class="ranks-rank">{rank}</span>'
            f'<span class="ranks-avatar" style="background:{identity_colour(identity)}" aria-hidden="true">'
            f'{escape(initials(name))}</span>'
            f'<span class="ranks-name">{escape(name)}{tag}{_tie_tag(rows, index)}</span>'
            f'<span class="ranks-points">{escape(format_points(points))}</span></li>'
        )
    st.markdown(markup + "</ol>", unsafe_allow_html=True)


def territory_pills(territories, names: dict, current_member: str) -> None:
    markup = '<div class="standings-pills" role="list" aria-label="Territory ownership">'
    for territory, owner, _rows in territories:
        if owner == current_member:
            status, title = "territory-yours", "Yours"
        elif owner:
            status, title = "territory-theirs", f"Owned by {names.get(owner, 'another player')}"
        else:
            status, title = "territory-free", "Unclaimed"
        markup += (
            f'<div class="standings-pill {status}" role="listitem" title="{escape(title)}">'
            f'<span class="standings-pill-dot {status}"></span><span>{escape(territory.name)}</span></div>'
        )
    st.markdown(markup + "</div>", unsafe_allow_html=True)
