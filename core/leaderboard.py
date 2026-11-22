"""Season-wide standings. Reuses the R-R01 replay algorithm from
territories.py instead of reimplementing tie-breaking here."""

from __future__ import annotations

from decimal import Decimal

from core.models import DrinkEntry
from core.territories import replay_leader


def _season_events(entries: list[DrinkEntry]) -> list[tuple]:
    return [
        (entry.submitted_at, entry.membership_id, entry.points_awarded)
        for entry in entries
        if entry.points_awarded > 0
    ]


def season_leader(entries: list[DrinkEntry], transfers=()) -> str | None:
    if transfers or any(entry.rule_version == "v1" for entry in entries):
        rows = season_leaderboard(entries, transfers)
        return rows[0][0] if rows else None
    return replay_leader(_season_events(entries))


def season_leaderboard(entries: list[DrinkEntry], transfers=()) -> list[tuple[str, int | Decimal]]:
    if transfers or any(entry.rule_version == "v1" for entry in entries):
        from core.scoring_v1 import replay_season
        return replay_season(entries, transfers).season_rows()
    # R-R01: equal totals rank by who reached that total first, i.e. whose last
    # scoring drink came earlier, the same order replay_leader uses for the leader.
    totals: dict[str, int] = {}
    reached: dict[str, int] = {}
    for position, (_ts, membership_id, points) in enumerate(
            sorted(_season_events(entries), key=lambda event: event[0])):
        totals[membership_id] = totals.get(membership_id, 0) + points
        reached[membership_id] = position
    return sorted(totals.items(), key=lambda item: (-item[1], reached[item[0]]))


# -- Game night ranking (Ranks tab: Season | Game night) ----------------------

def game_night_window(now, season):
    """The game night the Ranks tab shows: the one running now, else the most
    recent one (Thu 18:00 to Sun 18:00 by default, from the season's rules).
    Returns (start, end, is_current), or None when the season has not had a
    game night yet or uses the legacy rules (no scoring window)."""
    from datetime import timedelta
    from core.scoring_v1 import utc, window_bounds
    if getattr(season, "scoring_version", None) != "v1":
        return None
    at = min(utc(now), utc(season.ends_at) - timedelta(microseconds=1))
    start, end = window_bounds(at, season)
    if at < utc(start):                       # before this week's window: show last week's
        start, end = window_bounds(at - timedelta(days=7), season)
    if utc(end) <= utc(season.starts_at):
        return None
    return start, end, utc(start) <= utc(now) < utc(end)


def game_night_leaderboard(entries: list[DrinkEntry], competitors, start, end) -> list[tuple[str, int | Decimal]]:
    """Points from each competitor's own drinks checked in during one game
    night: the drink's season award (incl. any Time Duel bonus), but no owner
    income and no duel transfers. Every competitor is listed, 0 if they did
    not score. Ties go to whoever reached the tied total first (R-R01)."""
    from core.scoring_v1 import entry_order, utc
    from core.teams import competitor
    totals: dict[str, int | Decimal] = {c: 0 for c in competitors}
    reached: dict[str, tuple] = {}
    counted = [e for e in entries if e.points_awarded > 0 and e.location_check_result in ("matched", "outside")
               and utc(start) <= utc(e.submitted_at) < utc(end)]
    for entry in sorted(counted, key=entry_order):
        who = competitor(entry)
        totals[who] = totals.get(who, 0) + entry.points_awarded + (entry.time_bonus or 0)
        reached[who] = entry_order(entry)
    return sorted(totals.items(), key=lambda row: (-row[1], row[0] not in reached, reached.get(row[0], ()), row[0]))
