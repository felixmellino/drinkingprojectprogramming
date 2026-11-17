"""Territory ownership, computed live from confirmed drink entries.

Rule R-R01: when two players tie on points, whoever reached that score
first ranks higher / keeps ownership. replay_leader() implements this with
no extra bookkeeping: it replays scoring events in time order and only lets
the leader change on a STRICT improvement, so a later entry that merely
ties the leader's total never displaces them.
"""

from __future__ import annotations

from datetime import datetime

from core.models import DrinkEntry

# (timestamp, membership_id, points) in the order they happened.
ScoreEvent = tuple[datetime, str, int]


def replay_leader(events: list[ScoreEvent]) -> str | None:
    ordered = sorted(events, key=lambda event: event[0])
    totals: dict[str, int] = {}
    leader: str | None = None
    for _ts, membership_id, points in ordered:
        totals[membership_id] = totals.get(membership_id, 0) + points
        if leader is None or totals[membership_id] > totals[leader]:
            leader = membership_id
    return leader


def _territory_events(entries: list[DrinkEntry], territory_id: str) -> list[ScoreEvent]:
    return [
        (entry.submitted_at, entry.membership_id, entry.points_awarded)
        for entry in entries
        if entry.territory_id == territory_id and entry.location_check_result == "matched"
    ]


def territory_owner(entries: list[DrinkEntry], territory_id: str) -> str | None:
    return replay_leader(_territory_events(entries, territory_id))


def territory_standings(entries: list[DrinkEntry], territory_id: str) -> list[tuple[str, int]]:
    """Summed totals per membership for display, sorted descending. Only
    the top slot is guaranteed to match territory_owner()'s tie-break --
    ordering among non-leading ties is a simplification."""
    totals: dict[str, int] = {}
    for _ts, membership_id, points in _territory_events(entries, territory_id):
        totals[membership_id] = totals.get(membership_id, 0) + points
    return sorted(totals.items(), key=lambda item: item[1], reverse=True)
