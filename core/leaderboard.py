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
