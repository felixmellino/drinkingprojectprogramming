"""Build lobby activity from retained check-ins, captures and medal promotions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.medals import Promotion
from core.models import DrinkEntry
from core.scoring_v1 import entry_order, replay_season, utc
from core.teams import competitor

CHECKIN = "checkin"
CAPTURE = "capture"
MEDAL = "medal"


@dataclass(frozen=True)
class ActivityEvent:
    kind: str
    at: datetime                  # when the drink entry was submitted
    entry_id: str                 # the drink entry behind the event
    member: str                   # membership id of the player who drank
    competitor: str               # who scores: the member, or their team in team mode
    territory_id: str | None      # None for a check-in outside every territory
    points: int | float = 0       # check-ins only: base points plus any boost
    drink_type: str | None = None
    size: str | None = None
    previous_owner: str | None = None  # captures only: None when the territory was free
    medals: tuple[str, ...] = ()


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
    for entry_id, territory, new_owner, previous, _beaten in replay_season(entries).captures:
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


def with_promotions(events: list[ActivityEvent], promotions: list[Promotion]) -> list[ActivityEvent]:
    if not promotions:
        return events
    rows = [ActivityEvent(MEDAL, post.at, "", post.member, post.member, None, medals=post.medals)
            for post in promotions]
    return sorted(rows + events, key=lambda event: utc(event.at), reverse=True)
