"""Presentation helpers for the Drink Entries block; no game or data rules."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

import streamlit as st


def page_header(title: str, description: str = "", *, compact: bool = False, hide_title: bool = False) -> None:
    """Load page-scoped styles and an accessible heading (description optional).

    hide_title keeps the h1 for screen readers but not on screen, for pages
    whose content already makes clear where you are (the Leaderboard)."""
    css = (Path(__file__).parent / "assets" / "drink_entries.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    intro = f'<p class="drink-intro">{escape(description)}</p>' if description else ""
    hidden = ' class="sr-only"' if hide_title else ""
    st.markdown(
        f'<header class="drink-page-hero{" drink-camera-hero" if compact else ""}">'
        f'<h1{hidden}>{escape(title)}</h1>{intro}</header>',
        unsafe_allow_html=True,
    )


def section_heading(number: str, title: str, description: str = "") -> None:
    st.markdown(
        f'<div class="drink-section-heading"><h2>{escape(title)}</h2><p>{escape(description)}</p></div>',
        unsafe_allow_html=True,
    )


def context_line(label: str, detail: str) -> None:
    """Escape lobby/user values before inserting them into presentation HTML."""
    st.markdown(
        f'<div class="drink-context"><span>{escape(label)}</span><span>{escape(detail)}</span></div>',
        unsafe_allow_html=True,
    )


def reward_card_html(points: str, location: str, *, territory: str | None = None, captured: bool = False,
                     team_mode: bool = False, owner_income: str | None = None,
                     ownership_unavailable: bool = False) -> str:
    """One result card after an accepted check-in (layout "A: centred scoreboard").

    Every value is escaped here, so a territory or format string can never
    inject HTML. Formatting of the numbers happens in the caller.
    """
    zero = points in ("0", "+0")
    if zero:
        where = "Saved in your history with zero points."
    elif location == "outside":
        where = "Outside the game territories: season points only."
    elif territory:
        where = f"in {territory}"
    else:
        where = "Added to your season total."
    lines = [
        '<section class="reward-card" aria-label="Check-in result">',
        '<p class="reward-eyebrow">Drink posted</p>',
        f'<p class="reward-points{" reward-zero" if zero else ""}">+{escape(points)}</p>',
        '<p class="reward-unit">season points</p>',
        f'<p class="reward-where">{escape(where)}</p>',
    ]
    if captured and territory:
        who = "Your team captured" if team_mode else "You captured"
        lines.append(f'<p class="reward-chip">{escape(who)} {escape(territory)}!</p>')
    if owner_income:
        lines.append(f'<p class="reward-note">The previous owner also earned +{escape(owner_income)} season points.</p>')
    if ownership_unavailable:
        lines.append('<p class="reward-note">Your check-in was saved. The ownership update is unavailable; '
                     'check the Map or Leaderboard.</p>')
    lines.append("</section>")
    return "".join(lines)


def gate_card_html(eyebrow: str, big: str, line: str) -> str:
    """Shown instead of the camera when a check-in can't count right now
    (game night closed, season not running, or the cooldown). Same card
    shape as the reward card, with a muted number. Every value is escaped."""
    return (
        '<section class="reward-card gate-card" aria-label="Check-in not open">'
        f'<p class="reward-eyebrow">{escape(eyebrow)}</p>'
        f'<p class="reward-points reward-zero">{escape(big)}</p>'
        f'<p class="reward-where">{escape(line)}</p>'
        "</section>"
    )


_cooldown_timer = st.components.v2.component(
    "checkin_cooldown",
    html=gate_card_html("Next check-in in", "", ""),
    isolate_styles=False,
    js=(Path(__file__).parent / "components" / "checkin_cooldown.js").read_text(encoding="utf-8"),
)


def show_cooldown(now: datetime, deadline: datetime, seconds: int, *, has_photo: bool = False) -> None:
    """Render the live timer and let its expiry trigger a normal page rerun."""
    _cooldown_timer(
        key="checkin_cooldown",
        data={
            "deadline": deadline.isoformat(),
            "remainingMs": (deadline - now).total_seconds() * 1000,
            "limit": f"One drink every {seconds // 60} minutes.",
            "hasPhoto": has_photo,
        },
        on_expired_change=lambda: None,
    )
