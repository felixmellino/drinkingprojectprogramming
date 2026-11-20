"""Independent Decimal oracle and metamorphic checks, with reproducible seeds.

The oracle follows the written rules directly; it does not call scoring helpers.
These histories include exact fractional awards, absent owners, teams, ties,
outside entries and defensive rejection of invalid historical entries.
"""
from collections import defaultdict
from dataclasses import replace
from decimal import Decimal
import random
from types import SimpleNamespace

import pytest

from core.scoring_v1 import replay_season
from core.models import SeasonTransfer
from core.profile_stats import all_time_stats
from tests.test_scoring_v1 import START, entry


def reference(history):
    balances = defaultdict(Decimal)
    territories = defaultdict(lambda: defaultdict(Decimal))
    owners, income = {}, {}
    for item in sorted(history, key=lambda item: item.event_order):
        if item.points_awarded <= 0 or item.location_check_result not in ('matched', 'outside'):
            continue
        account = item.team_id or item.membership_id
        points = Decimal(str(item.points_awarded))
        area = item.territory_id if item.location_check_result == 'matched' else None
        prior_owner = owners.get(area)
        recipient = (prior_owner if prior_owner and prior_owner != account
                     and (item.team_id or prior_owner not in item.absent_member_ids) else None)
        bonus = points / 4 if recipient else Decimal(0)
        income[item.id] = (recipient, bonus)
        if recipient:
            balances[recipient] += bonus
        balances[account] += points + Decimal(str(item.time_bonus))
        if area:
            territories[area][account] += points
            # Strictly greater is essential: a tie keeps the earlier owner.
            if prior_owner is None or territories[area][account] > territories[area][prior_owner]:
                owners[area] = account
    return dict(balances), dict(territories), owners, income


def history(seed, teams):
    rng = random.Random(seed)
    records = []
    for index in range(100):
        member = rng.choice('ABCD')
        area = rng.choice(['north', 'south', 'west', None])
        item = entry(str(index), member, 'beer', 'small', index, territory=area, order=index)
        records.append(replace(item, points_awarded=rng.choice([1, 2, 3, 4, 5, 1.25, 1.5, 3.75]),
                               time_bonus=rng.choice([0, .25, .5]),
                               team_id=('one' if member in 'AB' else 'two') if teams else None,
                               absent_member_ids=tuple(rng.sample(list('ABCD'), rng.randrange(3)))))
    return records


@pytest.mark.parametrize('seed', range(12))
@pytest.mark.parametrize('teams', [False, True])
def test_random_histories_match_independent_oracle_and_conserve_points(seed, teams):
    records = history(seed, teams)
    balances, territories, owners, income = reference(records)
    replay = replay_season(records)
    actual = {account: Decimal(str(quarters)) / 4 for account, quarters in replay.season_quarters.items()}
    assert actual == balances, f'seed={seed}, teams={teams}'
    assert replay.owners == owners
    assert replay.territory_totals == territories
    assert {key: (owner, Decimal(str(quarters)) / 4) for key, (owner, quarters) in replay.awards.items()} == income
    source_points = sum(Decimal(str(item.points_awarded)) + Decimal(str(item.time_bonus)) for item in records)
    assert sum(actual.values()) == source_points + sum(value for _, value in income.values())
    assert sum(sum(values.values()) for values in territories.values()) == sum(
        Decimal(str(item.points_awarded)) for item in records if item.territory_id)
    # DB acceptance order, not query/network order, decides the result.
    random.Random(seed + 100).shuffle(records)
    assert replay_season(records) == replay
    # A rerun must not compound stored income or mutate source entries.
    assert replay_season(records) == replay
    assert all(item.owner_membership_id is None and item.owner_bonus_quarters == 0 for item in records)


def test_outside_entries_and_deleted_photos_do_not_change_territory_history():
    records = history(91, False)
    before = replay_season(records)
    outside = entry('outside', 'A', 'shot', None, 101, territory=None, order=101)
    after = replay_season(records + [outside])
    assert after.owners == before.owners and after.territory_totals == before.territory_totals
    assert sum(after.season_quarters.values()) == sum(before.season_quarters.values()) + 16
    assert replay_season([replace(item, photo_ref='', photo_captured_at=None) for item in records]) == before


def test_rejected_history_cannot_silently_award_points():
    valid = entry('valid', 'A', 'shot', None, 0, order=0)
    invalid = [replace(entry(str(i), 'B', 'shot', None, i, order=i), location_check_result=reason)
               for i, reason in enumerate(['unavailable', 'uncertain'], 1)]
    zero = replace(entry('zero', 'C', 'shot', None, 3, order=3), points_awarded=0)
    assert replay_season([valid, *invalid, zero]) == replay_season([valid])


@pytest.mark.parametrize('seed', range(6))
def test_stake_ledger_profile_and_rank_totals_agree_without_changing_territories(seed):
    records = history(seed + 200, False)
    expected, territories, owners, income = reference(records)
    before = replay_season(records)
    transfers = []
    for index in range(20):
        source, target = 'ABCD'[index % 4], 'ABCD'[(index + 1) % 4]
        points = 1 + index % 10
        assert expected[source] >= points
        transfers.append(SeasonTransfer(f'transfer-{index}', 'season', source, target,
                                        source, target, points, 100 + index, START))
        expected[source] -= points
        expected[target] += points
    after = replay_season(records, transfers)
    assert dict(after.season_rows()) == expected
    assert after.owners == owners and after.territory_totals == territories
    assert after.awards == before.awards  # Stakes never create territory income.
    assert sum(after.season_quarters.values()) == sum(before.season_quarters.values())
    wins = 0
    for member in 'ABCD':
        membership = [SimpleNamespace(id=member, lobby_id='lobby', team_id=None)]
        stats = all_time_stats(membership, records, transfers=transfers, finished_season_ids={'season'})
        season_only_bonus = sum(Decimal(str(item.time_bonus)) for item in records if item.membership_id == member)
        assert stats.points == expected[member] - season_only_bonus
        assert stats.drinks == sum(item.membership_id == member for item in records)
        assert stats == all_time_stats(membership, records * 2, transfers=transfers * 2,
                                      finished_season_ids={'season'})
        wins += stats.wins
    assert wins == 1
