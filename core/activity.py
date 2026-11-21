"""The lobby activity feed, derived from saved drink entries. No database or UI imports.

Nothing is stored for the feed: every event is rebuilt from the season's
accepted entries with the same replay that decides ownership on Ranks and
the Map (core/scoring_v1.replay_season). So the feed always agrees with the
standings, also after a correction changes history.

Version 1 has two kinds of event:
- "checkin": an accepted, scored drink entry;
- "capture": a territory changing owner (or a free territory being taken).
Later kinds (achievements, duel results, ...) add a new `kind` value.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.models import DrinkEntry
from core.scoring_v1 import entry_order, replay_season
from core.teams import competitor

CHECKIN = "checkin"
CAPTURE = "capture"


@dataclass(frozen=True)
class ActivityEvent:
    kind: str                     # CHECKIN or CAPTURE
    at: datetime                  # when the drink entry was submitted
    entry_id: str                 # the drink entry behind the event
    member: str                   # membership id of the player who drank
    competitor: str               # who scores: the member, or their team in team mode
    territory_id: str | None      # None for a check-in outside every territory
    points: int | float = 0       # check-ins only: base points plus any boost
    drink_type: str | None = None
    size: str | None = None
    previous_owner: str | None = None  # captures only: None when the territory was free


def accepted(entry: DrinkEntry) -> bool:
    """Only scored entries appear; the replay ignores everything else too."""
    return entry.points_awarded > 0 and entry.location_check_result in ("matched", "outside")


def activity_events(entries: list[DrinkEntry]) -> list[ActivityEvent]:
    """All events of one season, newest first.

    A capture is placed directly above the check-in that caused it, so the
    feed reads "Ben took Shortys" followed by Ben's drink.
    """
    if not entries:
        return []
    captures = {}
    for entry_id, territory, new_owner, previous in replay_season(entries).captures:
        captures[entry_id] = (territory, new_owner, previous)

    events: list[ActivityEvent] = []
    for entry in sorted(entries, key=entry_order):
        if not accepted(entry):
            continue
        territory = entry.territory_id if entry.location_check_result == "matched" else None
        events.append(ActivityEvent(CHECKIN, entry.submitted_at, entry.id, entry.membership_id,
                                    competitor(entry), territory, entry.points_awarded + entry.time_bonus,
                                    entry.drink_type, entry.size))
        if entry.id in captures:
            territory, new_owner, previous = captures[entry.id]
            events.append(ActivityEvent(CAPTURE, entry.submitted_at, entry.id, entry.membership_id,
                                        new_owner, territory, previous_owner=previous))
    events.reverse()
    return events
