"""Personal lifetime totals, with ownership and winners replayed per season."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from core.leaderboard import season_leader
from core.scoring_v1 import replay_season, utc


@dataclass(frozen=True)
class ProfileStats:
    points: Decimal
    drinks: int
    lobbies: int
    wins: int


@dataclass(frozen=True)
class Credit:
    member: str
    at: datetime
    points: Decimal
    drink: bool = False


def season_finished(season, now):
    """Only completed seasons can award a lifetime win."""
    return utc(season.ends_at) <= utc(now)


def season_credits(entries, transfers, *, finished):
    """Personal credits and the optional winner from the same season replay."""
    accepted = [entry for entry in {entry.id: entry for entry in entries}.values()
                if entry.points_awarded > 0 and entry.location_check_result in ("matched", "outside")]
    moves = list({transfer.id: transfer for transfer in transfers}.values())
    modern = any(entry.rule_version == "v1" for entry in accepted)
    snapshot = replay_season(accepted, moves) if modern else None
    credits = []
    for entry in accepted:
        credits.append(Credit(entry.membership_id, utc(entry.submitted_at),
                              Decimal(str(entry.points_awarded)), drink=True))
        if snapshot is not None:
            recipient, quarters = snapshot.awards[entry.id]
            if recipient:
                credits.append(Credit(recipient, utc(entry.submitted_at), Decimal(str(quarters)) / 4))
    for move in moves:
        if move.source_id == move.source_membership_id:
            credits.append(Credit(move.source_id, utc(move.created_at), Decimal(-move.points)))
        if move.target_id == move.target_membership_id:
            credits.append(Credit(move.target_id, utc(move.created_at), Decimal(move.points)))
    winner = None
    if finished:
        if snapshot is None:
            winner = season_leader(accepted, moves)
        else:
            rows = snapshot.season_rows()
            winner = rows[0][0] if rows else None
    return credits, winner


def all_time_stats(memberships, entries, *, finished_season_ids=(), transfers=()):
    """Count personal drinks plus individual owner income, with wins from finished seasons."""
    member_lobbies = {member.id: member.lobby_id for member in memberships}
    identities = {getattr(member, "team_id", None) or member.id for member in memberships}
    entries_by_season = defaultdict(list)
    moves_by_season = defaultdict(list)
    for entry in entries:
        entries_by_season[entry.season_id].append(entry)
    for move in transfers:
        moves_by_season[move.season_id].append(move)

    points = Decimal(0)
    drinks = wins = 0
    played = set()
    for season_id in entries_by_season.keys() | moves_by_season.keys():
        credits, winner = season_credits(entries_by_season[season_id], moves_by_season[season_id],
                                         finished=season_id in finished_season_ids)
        if winner in identities:
            wins += 1
        for credit in credits:
            if credit.member in member_lobbies:
                points += credit.points
                if credit.drink:
                    drinks += 1
                    played.add(member_lobbies[credit.member])
    return ProfileStats(points, drinks, len(played), wins)
