"""Build lobby activity from retained check-ins, captures, duel results and medal promotions."""

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
DUEL = "duel"

CHUG_DUEL = "Chug Duel"
QUIZ_DUEL = "Quiz Duel"
REACTION_DUEL = "Reaction Duel"
TIME_DUEL = "Time Duel"
TIME_DUEL_PRIZE = "×1.25"  # one hour of x1.25 on ordinary check-ins (R-M10)


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
    # Duels only: member/competitor above are the winner.
    game: str | None = None
    loser_member: str | None = None
    loser: str | None = None           # the loser's competitor (member or team)
    lost_points: int | float = 0       # what the loser gave up; 0 for a Time Duel
    prize: str | None = None           # shown instead of points (Time Duel boost)


def accepted(entry: DrinkEntry) -> bool:
    """Only scored entries appear; the replay ignores everything else too."""
    return entry.points_awarded > 0 and entry.location_check_result in ("matched", "outside")


def _chug_results(entries: list[DrinkEntry]) -> dict[str, tuple[DrinkEntry, DrinkEntry]]:
    """Finished Chug Duels: duel id -> (winner's entry, loser's entry).

    The loser's entry carries the winner's competitor in duel_transfer_to
    (R-M03). A duel without a recorded winner, or whose pair is incomplete,
    stays two ordinary check-ins.
    """
    pairs: dict[str, list[DrinkEntry]] = {}
    for entry in entries:
        if entry.duel_id and accepted(entry):
            pairs.setdefault(entry.duel_id, []).append(entry)
    results = {}
    for duel_id, pair in pairs.items():
        losers = [entry for entry in pair if entry.duel_transfer_to]
        if len(pair) != 2 or len(losers) != 1:
            continue
        loser = losers[0]
        winner = next(entry for entry in pair if entry is not loser)
        if competitor(winner) == loser.duel_transfer_to:
            results[duel_id] = (winner, loser)
    return results


def activity_events(entries: list[DrinkEntry], transfers=(), duel_results=None) -> list[ActivityEvent]:
    """All events of one season, newest first.

    A capture is placed directly above the check-in that caused it, so the
    feed reads "Ben took Shortys" followed by Ben's drink. A finished Chug Duel
    replaces its two drinks with one result row ("won, +2"); Quiz, Reaction
    and Time Duel results are slotted in at the time they finished.
    `transfers` is the season's stake ledger; `duel_results` comes from
    db.list_duel_results (None = not loaded: stake duels are then called "Duel").
    """
    if not entries and not transfers and not (duel_results or {}).get("time"):
        return []
    captures = {}
    if entries:
        for entry_id, territory, new_owner, previous, _beaten in replay_season(entries).captures:
            captures[entry_id] = (territory, new_owner, previous)
    chug = _chug_results(entries)

    def add_captures(entry):
        if entry.id in captures:
            territory, new_owner, previous = captures[entry.id]
            events.append(ActivityEvent(CAPTURE, entry.submitted_at, entry.id, entry.membership_id,
                                        new_owner, territory, previous_owner=previous))

    events: list[ActivityEvent] = []
    waiting: dict[str, DrinkEntry] = {}
    for entry in sorted(entries, key=entry_order):
        if not accepted(entry):
            continue
        territory = entry.territory_id if entry.location_check_result == "matched" else None
        if entry.duel_id in chug:
            if entry.duel_id not in waiting:
                waiting[entry.duel_id] = entry  # the result row follows the pair's second drink
                continue
            first = waiting.pop(entry.duel_id)
            winner, loser = chug[entry.duel_id]
            events.append(ActivityEvent(
                DUEL, max(first.submitted_at, entry.submitted_at, key=utc), winner.id, winner.membership_id,
                competitor(winner), territory,
                points=winner.points_awarded + winner.time_bonus + loser.points_awarded,
                drink_type=winner.drink_type, size=winner.size, game=CHUG_DUEL,
                loser_member=loser.membership_id, loser=competitor(loser), lost_points=loser.points_awarded))
            add_captures(first)
            add_captures(entry)
            continue
        events.append(ActivityEvent(CHECKIN, entry.submitted_at, entry.id, entry.membership_id,
                                    competitor(entry), territory, entry.points_awarded + entry.time_bonus,
                                    entry.drink_type, entry.size))
        add_captures(entry)
    events.reverse()
    return _merge_by_time(events, _timed_duels(transfers, duel_results))


def _timed_duels(transfers, duel_results) -> list[ActivityEvent]:
    """Quiz, Reaction and Time Duel results, newest first."""
    reaction_ids = (duel_results or {}).get("reaction_ids")
    rows = []
    for transfer in transfers:
        game = ("Duel" if reaction_ids is None else
                REACTION_DUEL if transfer.id in reaction_ids else QUIZ_DUEL)
        rows.append(ActivityEvent(DUEL, transfer.created_at, transfer.id, transfer.target_membership_id,
                                  transfer.target_id, None, points=transfer.points, game=game,
                                  loser_member=transfer.source_membership_id, loser=transfer.source_id,
                                  lost_points=transfer.points))
    for duel in (duel_results or {}).get("time", []):
        loser = duel["opponent_id"] if duel["winner_id"] == duel["challenger_id"] else duel["challenger_id"]
        rows.append(ActivityEvent(DUEL, duel["finished_at"], duel["id"], duel["winner_id"], duel["winner_id"],
                                  None, game=TIME_DUEL, loser_member=loser, loser=loser, prize=TIME_DUEL_PRIZE))
    return sorted(rows, key=lambda row: utc(row.at), reverse=True)


def _merge_by_time(events: list[ActivityEvent], rows: list[ActivityEvent]) -> list[ActivityEvent]:
    """Slot timed rows (newest first) into the newest-first feed.

    The check-ins and captures keep the replay order activity_events gave them;
    re-sorting them by timestamp could move a capture away from its check-in.
    A row at the same moment as a check-in goes above it.
    """
    merged, waiting = [], iter(rows)
    row = next(waiting, None)
    for event in events:
        while row is not None and utc(row.at) >= utc(event.at):
            merged.append(row)
            row = next(waiting, None)
        merged.append(event)
    if row is not None:
        merged += [row, *waiting]
    return merged


def with_promotions(events: list[ActivityEvent], promotions: list[Promotion]) -> list[ActivityEvent]:
    """Slot medal rows into the newest-first feed by time (see _merge_by_time)."""
    if not promotions:
        return events
    rows = sorted((ActivityEvent(MEDAL, post.at, "", post.member, post.member, None, medals=post.medals)
                   for post in promotions), key=lambda row: utc(row.at), reverse=True)
    return _merge_by_time(events, rows)
