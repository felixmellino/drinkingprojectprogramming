"""Read-only leaderboard presentation. Ranking comes from the core helpers."""

from html import escape
from pathlib import Path

import streamlit as st

from core.scoring_v1 import format_points


def load_styles() -> None:
    css = (Path(__file__).parent / "assets" / "standings.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def personal_summary(rank, points, owned, ranked_count: int, *, team_mode=False) -> None:
    cards = [
        ("Your team rank" if team_mode else "Your rank", f"#{rank}" if rank else "—", f"of {ranked_count} ranked {'teams' if team_mode else 'players'}" if rank else "No season points yet"),
        ("Team points" if team_mode else "Season points", format_points(points), "Your current total"),
        ("Territories", str(owned) if owned is not None else "—", "Currently yours" if owned is not None else "Could not load"),
    ]
    markup = '<section class="standings-summary" aria-label="Your season summary">'
    for label, value, detail in cards:
        markup += (f'<div class="standings-stat"><span>{escape(label)}</span>'
                   f'<strong>{escape(value)}</strong><small>{escape(detail)}</small></div>')
    st.markdown(markup + "</section>", unsafe_allow_html=True)


def leaderboard(rows, names: dict, current_member: str, owner_counts: dict, *, team_mode=False) -> None:
    """Render rows in precisely the order returned by season_leaderboard."""
    markup = ('<div class="standings-board"><table class="standings-table">'
              '<caption class="standings-sr-only">Season leaderboard, in ranking order</caption>'
              f'<thead><tr><th scope="col">Rank</th><th scope="col">{"Team" if team_mode else "Player"}</th>'
              '<th scope="col">Season points</th></tr></thead><tbody>')
    for rank, (member, points) in enumerate(rows, start=1):
        name = names.get(member, "Unknown player")
        is_you = member == current_member
        row_class = "standings-you" if is_you else ""
        medal = f" medal-{rank}" if rank <= 3 else ""
        badge = f'<span class="standings-you-tag">{"YOUR TEAM" if team_mode else "YOU"}</span>' if is_you else ""
        owned = owner_counts.get(member)
        detail = "Season leader" if rank == 1 else ""
        if owned is not None:
            territory_label = "territory" if owned == 1 else "territories"
            detail += (" · " if detail else "") + f"{owned} {territory_label}"
        markup += (f'<tr class="{row_class}"><td><span class="standings-rank{medal}">{rank}</span></td>'
                   f'<th scope="row"><div class="standings-player"><span class="standings-avatar" '
                   f'aria-hidden="true">{escape(name[:1].upper())}</span><div class="standings-player-text">'
                   f'<div class="standings-name">{escape(name)} {badge}</div><small>{escape(detail)}</small>'
                   f'</div></div></th><td class="standings-score">{escape(format_points(points))}'
                   '<span> pts</span></td></tr>')
    st.markdown(markup + "</tbody></table></div>", unsafe_allow_html=True)


def territory_cards(territories, names: dict, current_member: str) -> None:
    markup = '<section class="standings-territories" aria-label="Territory standings">'
    for territory, owner, rows in territories:
        owned_by_you = owner == current_member
        state = "Yours" if owned_by_you else "Claimed" if owner else "Unclaimed"
        card_class = " territory-yours" if owned_by_you else ""
        markup += (f'<article class="standings-territory{card_class}"><header><h3>{escape(territory.name)}</h3>'
                   f'<span class="territory-state">{state}</span></header>')
        if owner:
            markup += f'<p class="territory-owner">Owner <strong>{escape(names.get(owner, "Unknown player"))}</strong></p>'
        else:
            markup += '<p class="territory-empty">No owner yet. No territory points recorded.</p>'
        if rows:
            largest = max(points for _, points in rows)
            markup += '<ul class="territory-players">'
            for member, points in rows:
                width = max(0, min(100, points / largest * 100)) if largest > 0 else 0
                you = ' <span class="territory-you">(you)</span>' if member == current_member else ""
                markup += (f'<li><div><span>{escape(names.get(member, "Unknown player"))}{you}</span>'
                           f'<strong>{escape(format_points(points))} pts</strong></div>'
                           f'<div class="territory-track" aria-hidden="true"><span style="width:{width:.1f}%"></span></div></li>')
            markup += "</ul>"
        markup += "</article>"
    st.markdown(markup + "</section>", unsafe_allow_html=True)
