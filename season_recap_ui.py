"""Season recap presentation: the banner, the Lobby buttons and the animated story.

Which awards exist comes from core/season_recap.py. This module only turns them
into words and hands them to components/season_recap, which plays the slides.
"""
from __future__ import annotations

import csv
import io
import time
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError
from streamlit.components.v1 import declare_component

import data.db as db
from core.lobby_overview import lobby_status
from core.scoring_v1 import format_points, utc
from core.season_recap import CAPTURES, DRINKS, MVP, TAKEOVER, TERRITORIES, Recap, csv_rows
from theme import icon_url

RECAP_PAGE = "pages/9_Season_recap.py"
BANNER_DAYS = 14  # R-S03: the banner reminds for two weeks, the Lobby button stays
LOAD_ERRORS = (APIError, RequestError, RuntimeError, OSError)
ICONS = {MVP: "trophy", TERRITORIES: "map-trifold", TAKEOVER: "arrow-clockwise", CAPTURES: "skyline",
         DRINKS: "beer-stein", "you": "user-circle"}
TITLES = {MVP: "MVP", TERRITORIES: "Most territories held", TAKEOVER: "Biggest takeover",
          CAPTURES: "Most captures", DRINKS: "Most drinks"}

BANNER_CSS = (".st-key-season_recap_banner{background:var(--accent-soft);border-radius:var(--radius-lg);"
              "padding:12px 14px;margin-bottom:8px;gap:8px}"
              ".season-recap-banner-text{margin:0;color:var(--drink-ink);font-size:.95rem}")

_board = declare_component("season_recap", path=str(Path(__file__).parent / "components" / "season_recap"))


def plural(count, word: str, words: str | None = None) -> str:
    return f"{format_points(count)} {word if count == 1 else words or word + 's'}"


def ordinal(rank: int) -> str:
    suffix = "th" if 10 <= rank % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(rank % 10, "th")
    return f"{rank}{suffix}"


def season_dates(season) -> str:
    zone = ZoneInfo(season.timezone_name)
    start, end = (utc(t).astimezone(zone) for t in (season.starts_at, season.ends_at))
    return f"{start.day} {start:%b} to {end.day} {end:%b %Y}"


def award_text(award, names: dict, territory_names: dict, me: str | None) -> dict:
    """{'title', 'winner', 'detail'} in plain words; the viewer reads 'You'."""
    def who(competitor):
        return "You" if competitor == me else names.get(competitor, "Unknown player")
    detail = {
        MVP: plural(award.value, "point"),
        TERRITORIES: f"{plural(award.value, 'territory', 'territories')} at the end",
        CAPTURES: plural(award.value, "capture"),
        DRINKS: plural(award.value, "drink"),
    }.get(award.key)
    if award.key == TAKEOVER:
        victim = "you" if award.loser == me else names.get(award.loser, "another player")
        detail = (f"Took {territory_names.get(award.territory_id, 'a territory')} from {victim}, "
                  f"who had {plural(award.value, 'point')} there")
    return {"key": award.key, "title": TITLES[award.key], "winner": who(award.winner), "detail": detail}


def your_line(recap: Recap) -> dict:
    you = recap.you
    if you is None:
        return {"title": "Your season", "headline": "You didn't score this season",
                "detail": "Next season, every drink counts."}
    counts = [plural(you.drinks, "drink"),
              plural(you.territories, "territory", "territories") + " held",
              plural(you.captures, "capture")]
    return {"title": "Your season", "headline": f"You finished {ordinal(you.rank)} with {plural(you.points, 'point')}",
            "detail": ", ".join(counts)}


def recap_payload(recap: Recap, *, names: dict, territory_names: dict, me: str | None,
                  lobby_name: str, season) -> dict:
    """Everything the story slides show, as plain JSON-safe values."""
    return {
        "lobby": lobby_name,
        "dates": season_dates(season),
        "podium": [{"place": s.rank, "name": "You" if s.competitor == me else names.get(s.competitor, "Unknown player"),
                    "points": format_points(s.points)} for s in recap.podium],
        "awards": [award_text(a, names, territory_names, me) for a in recap.awards],
        "you": your_line(recap),
        "icons": {key: icon_url(name) for key, name in ICONS.items()},
    }


def csv_text(recap: Recap, names: dict) -> str:
    buffer = io.StringIO()
    csv.writer(buffer).writerows(csv_rows(recap, names))
    return buffer.getvalue()


def board(payload: dict, *, animate: bool, opened: str, key: str):
    from theme import component_tokens
    return _board(recap=payload, animate=animate, opened=opened, tokens=component_tokens(), key=key, default=None)


def open_recap(lobby_id: str, lobby_name: str, season_id: str, *, animate: bool) -> None:
    """Open the recap page for one season; the page checks access again."""
    st.session_state.update(_recap_season_id=season_id, _recap_lobby_id=lobby_id, _recap_lobby_name=lobby_name,
                            _recap_animate=animate, _recap_opened=str(time.time_ns()))
    st.switch_page(RECAP_PAGE)


def unfinished_recaps(rows, finished: set[str], now: datetime) -> list[tuple[str, str, str]]:
    """(lobby_id, lobby_name, season_id) of seasons that ended in the last two
    weeks and that this player has not finished yet, oldest first (R-S03)."""
    due = [(utc(season.ends_at), lobby.id, lobby.name, season.id) for lobby, _m, season in rows
           if season and lobby_status(season, now) == "past" and season.id not in finished
           and utc(now) - utc(season.ends_at) <= timedelta(days=BANNER_DAYS)]
    return [row[1:] for row in sorted(due)]


def finished_or_empty(player_id: str) -> set[str] | None:
    """None when the list can't be read (for example before migration 027):
    then no banner is shown rather than an error on every page."""
    try:
        return db.finished_recap_seasons(player_id)
    except LOAD_ERRORS:
        return None


def banner() -> None:
    """'Your season in X is over' on every page until the player finishes it."""
    from app_navigation import current_page
    pending = st.session_state.get("_unfinished_recaps") or []
    if not pending or current_page() == "season_recap":
        return
    lobby_id, lobby_name, season_id = pending[0]
    with st.container(key="season_recap_banner"):
        st.markdown(f"<style>{BANNER_CSS}</style>"
                    f'<p class="season-recap-banner-text"><strong>Your season in {escape(lobby_name)} is over.</strong> '
                    "See who won and collect the awards.</p>", unsafe_allow_html=True)
        if st.button("Finish season", key="season_recap_banner_open", type="primary"):
            open_recap(lobby_id, lobby_name, season_id, animate=True)


def lobby_button(lobby, season, finished: set[str] | None) -> None:
    """On a past lobby card: Finish season first, Season awards afterwards."""
    if not season:
        return
    # When the list can't be read, never push an animation that can't be saved.
    done = finished is None or season.id in finished
    label, animate = ("Season awards", False) if done else ("Finish season", True)
    # The lobby_select_ key puts it in the card's bottom-left slot (assets/lobbies.css),
    # where Make current sits on running lobbies, so it never covers View lobby.
    with st.container(key=f"lobby_select_recap_{lobby.id}"):
        if st.button(label, key=f"season_recap_{lobby.id}", type="secondary" if done else "primary"):
            open_recap(lobby.id, lobby.name, season.id, animate=animate)


def mark_finished(season_id: str) -> None:
    st.session_state["_unfinished_recaps"] = [row for row in st.session_state.get("_unfinished_recaps") or []
                                              if row[2] != season_id]


