"""One rank ladder for each lifetime statistic and its lobby promotions."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from core.profile_stats import ProfileStats, season_credits, season_finished
from core.scoring_v1 import utc

RANKS = ("Newcomer", "Beginner", "Regular", "Contender", "Expert", "Veteran", "Master", "Legend")
CATEGORIES = {
    "points": ("Total points", (0, 1, 10, 25, 50, 100, 250, 500)),
    "drinks": ("Drinks", (0, 1, 5, 10, 20, 35, 60, 100)),
    "lobbies": ("Lobbies played", (0, 1, 2, 3, 5, 8, 12, 20)),
    "wins": ("Total Wins", (0, 1, 2, 3, 4, 5, 8, 12)),
}


def rank_index(category, total):
    return sum(total >= threshold for threshold in CATEGORIES[category][1][1:])


def medal_cards(stats: ProfileStats):
    for category, (label, thresholds) in CATEGORIES.items():
        total = getattr(stats, category)
        rank = rank_index(category, total)
        next_goal = thresholds[rank + 1] if rank + 1 < len(thresholds) else None
        yield label, total, rank, next_goal


@dataclass(frozen=True)
class Promotion:
    member: str
    at: datetime
    medals: tuple[str, ...]


@dataclass
class _Change:
    points: Decimal = Decimal(0)
    drinks: int = 0
    wins: int = 0


def lobby_promotions(lobby_id, memberships, history, *, launched_at, now):
    """Build announcements from retained records, including earlier history as a baseline.

    History holds (season, entries, transfers) for the target players' lobbies.
    Only promotions earned in the requested lobby leave this function.
    """
    members = {member.id: member for member in memberships}
    by_lobby = defaultdict(list)
    for member in members.values():
        by_lobby[member.lobby_id].append(member)
    changes = defaultdict(_Change)
    for season, entries, transfers in history:
        credits, winner = season_credits(entries, transfers, finished=season_finished(season, now))
        for credit in credits:
            if credit.member in members and credit.at <= utc(now):
                change = changes[credit.at, season.lobby_id, credit.member]
                change.points += credit.points
                change.drinks += credit.drink
        for member in by_lobby[season.lobby_id]:
            if winner == (member.team_id or member.id):
                changes[utc(season.ends_at), season.lobby_id, member.id].wins += 1

    totals = defaultdict(_Change)
    played = defaultdict(set)
    best = defaultdict(int)
    promotions = []
    for (at, source_lobby, member_id), change in sorted(changes.items()):
        player = members[member_id].player_id
        total = totals[player]
        total.points += change.points
        total.drinks += change.drinks
        total.wins += change.wins
        if change.drinks:
            played[player].add(source_lobby)
        stats = ProfileStats(total.points, total.drinks, len(played[player]), total.wins)
        earned = []
        for category, (label, _) in CATEGORIES.items():
            rank = rank_index(category, getattr(stats, category))
            key = player, category
            if rank > best[key]:
                best[key] = rank
                earned.append(f"{RANKS[rank]} in {label.lower()}")
        if earned and source_lobby == lobby_id and at >= utc(launched_at):
            promotions.append(Promotion(member_id, at, tuple(earned)))
    return promotions
