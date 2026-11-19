"""Read-only leaderboard presentation. Ranking comes from the core helpers."""

from html import escape
from pathlib import Path

import streamlit as st

from core.profile_photo import initials
from core.scoring_v1 import format_points


def load_styles() -> None:
    css = (Path(__file__).parent / "assets" / "standings.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def _podium_place(rank: int, member: str, points, names: dict, current_member: str, *, team_mode: bool) -> str:
    name = names.get(member, "Unknown player")
    you = member == current_member
    size = {1: ("52px", "92px", "15px"), 2: ("42px", "66px", "13px"), 3: ("42px", "48px", "13px")}[rank]
    avatar_size, block_height, name_size = size
    avatar_ring = "box-shadow:0 0 0 3px var(--brand-ink);" if rank == 1 else ""
    avatar_fill = "background:var(--accent);color:var(--on-accent);" if you else "background:var(--accent-soft);color:var(--text);"
    block_fill = "background:var(--accent);" if rank == 1 else "background:var(--surface);box-shadow:var(--shadow-card);"
    numeral_color = {1: "var(--brand-ink)", 2: "var(--medal-2)", 3: "var(--medal-3)"}[rank]
    tag = f'<span class="standings-podium-tag">{"YOUR TEAM" if team_mode else "YOU"}</span>' if you else ""
    return (
        f'<li class="standings-podium-place standings-podium-{rank}">'
        f'<span class="standings-podium-avatar" style="width:{avatar_size};height:{avatar_size};{avatar_fill}{avatar_ring}" aria-hidden="true">{escape(initials(name))}</span>'
        f'<span class="standings-podium-name" style="font-size:{name_size}">{escape(name)}{tag}</span>'
        f'<span class="standings-podium-points">{escape(format_points(points))}<small> pts</small></span>'
        f'<span class="standings-podium-block" style="height:{block_height};{block_fill}">'
        f'<span style="color:{numeral_color}">{rank}</span></span></li>'
    )


def leaderboard(rows, names: dict, current_member: str, *, team_mode: bool = False) -> None:
    """Render rows in precisely the order returned by season_leaderboard: a
    podium for the top 3, then a flat ranked list for the rest."""
    podium = rows[:3]
    rest = rows[3:]

    if podium:
        ranked = dict(enumerate(podium, start=1))
        places = "".join(
            _podium_place(rank, *ranked[rank], names, current_member, team_mode=team_mode)
            for rank in (2, 1, 3) if rank in ranked
        )
        st.markdown(f'<ol class="standings-podium" aria-label="Top 3 this season">{places}</ol>', unsafe_allow_html=True)

    if rest:
        markup = '<ol class="standings-list" start="4">'
        for offset, (member, points) in enumerate(rest):
            rank = offset + 4
            name = names.get(member, "Unknown player")
            you = member == current_member
            row_class = " standings-row-you" if you else ""
            avatar_fill = "background:var(--accent);color:var(--on-accent);" if you else "background:var(--accent-soft);color:var(--text);"
            tag = f'<span class="standings-you-tag">{"YOUR TEAM" if team_mode else "YOU"}</span>' if you else ""
            markup += (
                f'<li class="standings-row{row_class}"><span class="standings-row-rank">{rank}</span>'
                f'<span class="standings-row-avatar" style="{avatar_fill}" aria-hidden="true">{escape(initials(name))}</span>'
                f'<span class="standings-row-name">{escape(name)}{tag}</span>'
                f'<span class="standings-row-points">{escape(format_points(points))}</span></li>'
            )
        st.markdown(markup + "</ol>", unsafe_allow_html=True)


def _pills(items) -> str:
    markup = '<div class="standings-pills" role="list" aria-label="Territory ownership">'
    for name, status, title in items:
        markup += (
            f'<div class="standings-pill" role="listitem" title="{escape(title)}">'
            f'<span class="standings-pill-dot {status}"></span><span>{escape(name)}</span></div>'
        )
    return markup + "</div>"


def territory_pills(territories, names: dict, current_member: str) -> None:
    """Territories section: counts, the claimed areas as chips (yours first),
    and the unclaimed ones folded away."""
    claimed, free = [], []
    for territory, owner, _rows in territories:
        if owner == current_member:
            claimed.append((0, territory.name, "territory-yours", "Yours"))
        elif owner:
            claimed.append((1, territory.name, "territory-theirs", f"Owned by {names.get(owner, 'another player')}"))
        else:
            free.append((territory.name, "territory-free", "Unclaimed"))
    yours = sum(1 for item in claimed if item[0] == 0)
    st.markdown(
        '<div class="standings-section"><h2>Territories</h2>'
        f'<p><b class="territory-yours-text">{yours}</b> yours · <b class="territory-theirs-text">{len(claimed) - yours}</b> rivals · '
        f'<b>{len(free)}</b> free</p></div>',
        unsafe_allow_html=True,
    )
    if claimed:
        st.markdown(_pills(item[1:] for item in sorted(claimed)), unsafe_allow_html=True)
    if free:
        with st.expander(f"Free territories ({len(free)})"):
            st.markdown(_pills(sorted(free)), unsafe_allow_html=True)
