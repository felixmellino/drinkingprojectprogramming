"""Season recap presentation: the Lobby buttons and the animated story.

Which awards exist comes from core/season_recap.py. This module only turns them
into words and hands them to components/season_recap, which plays the slides.
"""
from __future__ import annotations

import csv
import io
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError
from streamlit.components.v1 import declare_component

import data.db as db
from core.scoring_v1 import format_points, utc
from core.season_recap import CAPTURES, DRINKS, MVP, TAKEOVER, TERRITORIES, Recap, csv_rows
from theme import icon_url

RECAP_PAGE = "pages/9_Season_recap.py"
RANKS_PAGE = "pages/4_Standings.py"
LOAD_ERRORS = (APIError, RequestError, RuntimeError, OSError)
ICONS = {MVP: "trophy", TERRITORIES: "map-trifold", TAKEOVER: "arrow-clockwise", CAPTURES: "skyline",
         DRINKS: "beer-stein", "you": "user-circle"}
TITLES = {MVP: "MVP", TERRITORIES: "Most territories held", TAKEOVER: "Biggest takeover",
          CAPTURES: "Most captures", DRINKS: "Most drinks"}

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


def open_recap(lobby_id: str, lobby_name: str, season_id: str, *, animate: bool,
               return_to: str | None = None) -> None:
    """Open the recap page for one season; the page checks access again.
    Close returns to return_to, otherwise to the Lobby page."""
    st.session_state["_recap_return"] = return_to
    st.session_state.update(_recap_season_id=season_id, _recap_lobby_id=lobby_id, _recap_lobby_name=lobby_name,
                            _recap_animate=animate, _recap_opened=str(time.time_ns()))
    st.switch_page(RECAP_PAGE)


def summary_pending(player_id: str, season) -> bool:
    """R-S03: the season has ended and this player has not closed its recap yet.

    While True, the lobby's pages send the player to Ranks to watch the summary.
    A season this session saw finished is remembered, so pages read the history
    only while the summary is still due. If the history can't be read (for
    example before migration 029), nobody is held back: the recap could not be saved.
    """
    if season is None or datetime.now(timezone.utc) < utc(season.ends_at):
        return False
    seen = st.session_state.setdefault("_recap_seen", set())
    if (player_id, season.id) in seen:
        return False
    finished = finished_or_empty(player_id)
    if finished is None or season.id in finished:
        seen.add((player_id, season.id))
        return False
    return True


def mark_seen(player_id: str, season_id: str) -> None:
    st.session_state.setdefault("_recap_seen", set()).add((player_id, season_id))


def finished_notice() -> None:
    """Map, Check in, Games, Activity and photos while the summary is due."""
    st.info("This season is finished. Watch the summary on Ranks to see who won.")
    if st.button("Go to Ranks", key="season_finished_go_to_ranks", type="primary"):
        st.switch_page(RANKS_PAGE)


def finished_card(lobby_id: str, lobby_name: str, season) -> None:
    """Ranks while the summary is due: only the finished card and Watch summary."""
    with st.container(border=True, key="season_finished_card"):
        st.markdown("### The season is finished")
        st.caption(f"{lobby_name}, {season_dates(season)}. See who won and collect the awards.")
        if st.button("Watch summary", key="season_finished_watch", type="primary", width="stretch"):
            open_recap(lobby_id, lobby_name, season.id, animate=True, return_to=RANKS_PAGE)


def finished_or_empty(player_id: str) -> set[str] | None:
    """Return None when recap history is unavailable, for example before migration 029."""
    try:
        return db.finished_recap_seasons(player_id)
    except LOAD_ERRORS:
        return None


def lobby_button(lobby, season, finished: set[str] | None, *, is_admin: bool) -> None:
    """Offer the first-view story to the lobby admin and awards to members."""
    if not season:
        return
    # When the list can't be read, never push an animation that can't be saved.
    animate = is_admin and finished is not None and season.id not in finished
    label = "Finish season" if animate else "Season awards"
    # Drawn inside the card's bottom-left slot (lobby_ui), beside Make current.
    if st.button(label, key=f"season_recap_{lobby.id}", type="primary" if animate else "secondary"):
        open_recap(lobby.id, lobby.name, season.id, animate=animate)
