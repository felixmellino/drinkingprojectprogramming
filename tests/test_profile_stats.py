from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

from core.profile_stats import all_time_stats, lobby_finished
from tests.test_scoring_v1 import entry


def test_personal_income_replay_corrections_and_season_isolation():
    members = [SimpleNamespace(id='me', lobby_id='lobby')]
    own = entry('a', 'me', 'beer', 'large', 0)
    visitor = entry('b', 'other', 'beer', 'small', 1)
    # Stored bonuses can be stale after correction; recompute from source.
    visitor.owner_bonus_quarters = 99
    second_season = replace(entry('c', 'other', 'beer', 'large', 2), season_id='second')
    stats = all_time_stats(members, [own, visitor, second_season, own])
    assert stats.points == Decimal('3.25')
    assert (stats.drinks, stats.lobbies, stats.wins) == (1, 1, 1)
    corrected = replace(own, membership_id='other')
    assert all_time_stats(members, [corrected, visitor]).points == 0


def test_legacy_outside_invalid_and_nonpositive_entries():
    members = [SimpleNamespace(id='me', lobby_id='lobby')]
    own = replace(entry('a', 'me', 'beer', 'large', 0, territory=None), rule_version='legacy')
    rejected = replace(own, id='bad', location_check_result='uncertain')
    zero = replace(own, id='zero', points_awarded=0)
    stats = all_time_stats(members, [own, rejected, zero])
    assert (stats.points, stats.drinks, stats.lobbies) == (3, 1, 1)


def test_empty_history():
    stats = all_time_stats([], [])
    assert (stats.points, stats.drinks, stats.lobbies, stats.wins) == (0, 0, 0, 0)


def test_finish_boundary_and_incomplete_lobby():
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    ended = SimpleNamespace(ends_at=now)
    active = SimpleNamespace(ends_at=now + timedelta(microseconds=1))
    assert lobby_finished([ended], now)
    assert not lobby_finished([ended, active], now)
    assert not lobby_finished([], now)


def test_multiple_seasons_one_lobby_and_existing_tie_break():
    members = [SimpleNamespace(id='me', lobby_id='lobby')]
    first = entry('a', 'me', 'beer', 'large', 0)
    tie = entry('b', 'other', 'beer', 'large', 1, territory=None)
    second = replace(first, id='c', season_id='next')
    stats = all_time_stats(members, [first, tie, second])
    assert (stats.points, stats.drinks, stats.lobbies, stats.wins) == (6, 2, 1, 2)


def test_team_win_without_own_drinks_does_not_copy_team_points():
    members = [SimpleNamespace(id='me', lobby_id='lobby', team_id='team')]
    teammate = replace(entry('a', 'other', 'beer', 'large', 0), team_id='team')
    stats = all_time_stats(members, [teammate])
    assert (stats.points, stats.drinks, stats.lobbies, stats.wins) == (0, 0, 0, 1)
