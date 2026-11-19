"""Read-only leaderboard presentation. Ranking comes from the core helpers."""

from html import escape
from pathlib import Path

import streamlit as st

from core.profile_photo import initials
from theme import page_subtitle
from core.scoring_v1 import format_points


def load_styles() -> None:
    css = (Path(__file__).parent / "assets" / "standings.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# Top three: rank number in the medal colour (tokens in assets/theme.css).
MEDALS = {1: "standings-medal-1", 2: "standings-medal-2", 3: "standings-medal-3"}


def subtitle(lobby_name: str, members: int, ranked: int, phase: str | None = None, *, team_mode: bool = False) -> None:
    """One quiet line under the title: lobby and size; the season phase
    (finished or upcoming) as a caption when the season isn't running."""
    parts = [lobby_name, f"{members} members", f"{ranked} teams ranked"] if team_mode else [lobby_name, f"{members} players"]
    page_subtitle(*parts)
    if phase:
        st.caption(phase)


def leaderboard(rows, names: dict, current_member: str, *, team_mode: bool = False) -> None:
    """Every rank in one clean list, in exactly the order season_leaderboard
    returns. The top three are marked only by the colour of their number."""
    markup = '<ol class="standings-list" aria-label="Season ranking">'
    for rank, (member, points) in enumerate(rows, start=1):
        name = names.get(member, "Unknown player")
        you = member == current_member
        row_class = " standings-row-you" if you else ""
        tag = f'<span class="standings-you-tag">{"your team" if team_mode else "you"}</span>' if you else ""
        markup += (
            f'<li class="standings-row{row_class}">'
            f'<span class="standings-row-rank {MEDALS.get(rank, "")}">{rank}</span>'
            f'<span class="standings-row-avatar" aria-hidden="true">{escape(initials(name))}</span>'
            f'<span class="standings-row-name">{escape(name)}{tag}</span>'
            f'<span class="standings-row-points">{escape(format_points(points))}</span></li>'
        )
    st.markdown(markup + "</ol>", unsafe_allow_html=True)


def territory_pills(territories, names: dict, current_member: str) -> None:
    """Territories: one row with the counts that opens the full list
    (yours first, then rivals', then the free ones)."""
    rows = []
    for territory, owner, _rows in territories:
        if owner == current_member:
            rows.append((0, territory.name, "territory-yours", "Yours", "Yours"))
        elif owner:
            owner_name = names.get(owner, "another player")
            rows.append((1, territory.name, "territory-theirs", f"Owned by {owner_name}", owner_name))
        else:
            rows.append((2, territory.name, "territory-free", "Unclaimed", "Free"))
    rows.sort()
    counts = [sum(1 for r in rows if r[0] == group) for group in (0, 1, 2)]
    st.markdown('<p class="standings-label">Territories</p>', unsafe_allow_html=True)
    with st.expander(f"{counts[0]} yours · {counts[1]} rivals · {counts[2]} free"):
        markup = '<ul class="standings-territories" aria-label="Territory ownership">'
        for _group, name, status, title, owner_text in rows:
            markup += (
                f'<li class="standings-territory" title="{escape(title)}">'
                f'<span class="standings-pill-dot {status}"></span><span class="standings-territory-name">{escape(name)}</span>'
                f'<span class="standings-territory-owner">{escape(owner_text)}</span></li>'
            )
        st.markdown(markup + "</ul>", unsafe_allow_html=True)
