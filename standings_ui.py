"""Read-only leaderboard presentation. Ranking comes from the core helpers."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from decimal import Decimal
from html import escape
from pathlib import Path

import streamlit as st

from core.scoring_v1 import DRINK_LABELS, format_points
from core.teams import competitor
from photo_history_ui import identity_colour
from profile_picture_ui import avatar_html


def load_styles() -> None:
    css = (Path(__file__).parent / "assets" / "standings.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def reached_first(rows, index: int) -> bool:
    """True when the row below has the same points: this row ranks higher only
    because it reached the score first."""
    # Players still on 0 have not reached anything (game night view lists them too).
    return (index + 1 < len(rows) and Decimal(str(rows[index][1])) > 0
            and Decimal(str(rows[index][1])) == Decimal(str(rows[index + 1][1])))


def _tie_tag(rows, index: int) -> str:
    return '<span class="standings-first-tag">reached first</span>' if reached_first(rows, index) else ""


def _podium_place(rank: int, member: str, points, names: dict, current_member: str, *, team_mode: bool,
                  extras: str = "", picture: str | None = None) -> str:
    name = names.get(member, "Unknown player")
    you = member == current_member
    size = {1: ("48px", "124px", "16px"), 2: ("40px", "92px", "14px"), 3: ("40px", "68px", "14px")}[rank]
    avatar_size, block_height, name_size = size
    # Blocks: 1st our sky blue, 2nd silver, 3rd bronze; the numerals stay dark ink.
    medal = {1: "var(--accent)", 2: "var(--medal-2)", 3: "var(--medal-3)"}[rank]
    block_fill = f"background:{medal};"
    # The avatar keeps the player's own identity colour (same as their row and
    # photo frames), ringed in the colour of their podium step.
    identity = {"team_id": member} if team_mode else {"membership_id": member}
    avatar_fill = f"background:{identity_colour(identity)};color:#fff;"
    avatar_ring = f"box-shadow:0 0 0 3px var(--bg), 0 0 0 6px {medal};"
    numeral_color = "var(--text)"
    tag = f'<span class="standings-podium-tag">{"YOUR TEAM" if team_mode else "YOU"}</span>' if you else ""
    return (
        f'<div class="standings-podium-place standings-podium-{rank}">'
        + avatar_html(name, picture, cls="standings-podium-avatar",
                      style=f"width:{avatar_size};height:{avatar_size};{avatar_fill}{avatar_ring}") +
        f'<span class="standings-podium-name" style="font-size:{name_size}">{escape(name)}{tag}{extras}</span>'
        f'<span class="standings-podium-points">{escape(format_points(points))}</span>'
        f'<span class="standings-podium-block" style="height:{block_height};{block_fill}">'
        f'<span style="color:{numeral_color}">{rank}</span></span></div>'
    )


def _row(rank: int, member: str, points, rows, names: dict, current_member: str, *, team_mode: bool,
         picture: str | None = None) -> str:
    name = names.get(member, "Unknown player")
    you = member == current_member
    row_class = " standings-row-you" if you else ""
    # Same hashed per-player colour as their photo-history frames,
    # so a face recurring across pages reads as the same identity.
    identity = {"team_id": member} if team_mode else {"membership_id": member}
    avatar_fill = f"background:{identity_colour(identity)};color:#fff;"
    tag = f'<span class="standings-you-tag">{"YOUR TEAM" if team_mode else "YOU"}</span>' if you else ""
    return (
        f'<div class="standings-row{row_class}"><span class="standings-row-rank">{rank}</span>'
        + avatar_html(name, picture, cls="standings-row-avatar", style=avatar_fill) +
        f'<span class="standings-row-name">{escape(name)}{tag}{_tie_tag(rows, rank - 1)}</span>'
        f'<span class="standings-row-points">{escape(format_points(points))}</span></div>'
    )


def _tap(rank: int, member: str, names: dict) -> bool:
    """An invisible full-size button over a podium place or row (same trick as
    the photo grid). Its label stays readable for screen readers."""
    return st.button(f"Show {names.get(member, 'player')}'s profile", key=f"rank_tap_btn_{rank}")


def leaderboard(rows, names: dict, current_member: str, *, team_mode: bool = False,
                pictures: dict | None = None) -> str | None:
    """Render rows in precisely the order returned by season_leaderboard: a
    podium for the top 3, then one card per player. Every place is tappable;
    returns the tapped member/team id (None when nothing was tapped)."""
    tapped = None
    podium = rows[:3]
    if podium:
        ranked = dict(enumerate(podium, start=1))
        order = [rank for rank in (2, 1, 3) if rank in ranked]
        with st.container(key="rank_podium"):
            for column, rank in zip(st.columns(len(order), vertical_alignment="bottom", gap="small"), order):
                member, points = ranked[rank]
                with column, st.container(key=f"rank_tap_{rank}"):
                    st.markdown(_podium_place(rank, member, points, names, current_member, team_mode=team_mode,
                                              extras=_tie_tag(rows, rank - 1),
                                              picture=(pictures or {}).get(member)), unsafe_allow_html=True)
                    if _tap(rank, member, names):
                        tapped = member
    if rows[3:]:
        with st.container(key="rank_list"):
            for offset, (member, points) in enumerate(rows[3:]):
                rank = offset + 4
                with st.container(key=f"rank_tap_{rank}"):
                    st.markdown(_row(rank, member, points, rows, names, current_member, team_mode=team_mode,
                                     picture=(pictures or {}).get(member)), unsafe_allow_html=True)
                    if _tap(rank, member, names):
                        tapped = member
    return tapped


def player_stats(member: str, entries, owners: dict | None, territory_names: dict) -> dict:
    """What the player sheet shows, from the season's already-loaded entries.
    owners maps territory id -> owner (None when territories are unavailable).
    Only accepted, scored check-ins count; the last one shows its territory,
    never a location."""
    mine = [e for e in entries if competitor(e) == member and e.points_awarded > 0
            and e.location_check_result in ("matched", "outside")]
    counts = Counter(e.drink_type for e in mine)
    favourite = None
    if counts:
        latest = {e.drink_type: e.submitted_at for e in mine}
        kind = max(counts, key=lambda k: (counts[k], latest[k]))  # ties: the most recent kind
        favourite = DRINK_LABELS.get(kind, kind.title())
    last = max(mine, key=lambda e: e.submitted_at, default=None)
    place = None
    if last is not None:
        place = (territory_names.get(last.territory_id, "A territory") if last.location_check_result == "matched"
                 else "Outside the map")
    return {
        "drinks": len(mine),
        "territories": None if owners is None else sum(1 for owner in owners.values() if owner == member),
        "favourite": favourite,
        "last_place": place,
        "last_at": last.submitted_at if last else None,
    }


def ago(when: datetime | None, now: datetime) -> str:
    if when is None:
        return ""
    minutes = int((now - when).total_seconds() // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    if minutes < 24 * 60:
        return f"{minutes // 60} h ago"
    return f"{when:%a %d %b}"


def player_sheet_html(name: str, rank: int, points, stats: dict, now: datetime) -> str:
    """Body of the bottom sheet (layout A). Every value is escaped."""
    def tile(label, value, sub=""):
        sub_html = f"<em>{escape(sub)}</em>" if sub else ""
        return f'<div class="sheet-stat"><small>{escape(label)}</small><b>{escape(str(value))}</b>{sub_html}</div>'
    territories = "—" if stats["territories"] is None else stats["territories"]
    return (
        f'<div class="sheet-head"><p class="sheet-rank">Rank {rank} with {escape(format_points(points))} points</p></div>'
        '<div class="sheet-grid">'
        + tile("Drinks", stats["drinks"])
        + tile("Territories", territories)
        + tile("Favourite", stats["favourite"] or "—")
        + tile("Last check-in", stats["last_place"] or "—", ago(stats["last_at"], now))
        + "</div>"
    )


def player_sheet(name: str, rank: int, points, stats: dict, now: datetime) -> None:
    """Bottom sheet on phones (a centred dialog on laptops)."""
    def body():
        st.markdown(player_sheet_html(name, rank, points, stats, now), unsafe_allow_html=True)
        # Tapping outside or the x closes it in the browser; Close needs a rerun.
        if st.button("Close", key="rank_sheet_close", type="primary", width="stretch"):
            st.rerun()
    st.dialog(name, dismissible=True)(body)()


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
