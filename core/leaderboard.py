"""Season-wide standings. Reuses the R-R01 replay algorithm from
territories.py instead of reimplementing tie-breaking here."""

from __future__ import annotations

from core.models import DrinkEntry
from core.territories import replay_leader


def _season_events(entries: list[DrinkEntry]) -> list[tuple]:
    return [
        (entry.submitted_at, entry.membership_id, entry.points_awarded)
        for entry in entries
        if entry.points_awarded > 0
    ]


def season_leader(entries: list[DrinkEntry]) -> str | None:
    return replay_leader(_season_events(entries))


def season_leaderboard(entries: list[DrinkEntry]) -> list[tuple[str, int]]:
    totals: dict[str, int] = {}
    for _ts, membership_id, points in _season_events(entries):
        totals[membership_id] = totals.get(membership_id, 0) + points
    return sorted(totals.items(), key=lambda item: item[1], reverse=True)
