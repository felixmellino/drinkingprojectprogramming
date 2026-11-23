from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

import data.db as db
from core.scoring_v1 import checkin_open, create_scored_entry, new_rules, next_opening, scoring_open
from core.checkins import CheckinRejected
from core.chug_duel import duel_open
from tests.test_scoring_v1 import season
from tests.test_checkins import INSIDE, TERRITORY

WEDNESDAY = datetime(2026, 11, 18, 8, tzinfo=timezone.utc)


def qa_season(zone='Europe/Lisbon'):
    return replace(season(zone), starts_at=WEDNESDAY-timedelta(days=1), scoring_rules=new_rules(test_mode=True))


@pytest.mark.parametrize('at,allowed', [(WEDNESDAY-timedelta(microseconds=1), False),
    (WEDNESDAY, True), (WEDNESDAY+timedelta(days=4,hours=10)-timedelta(microseconds=1), True),
    (WEDNESDAY+timedelta(days=4,hours=10), False)])
def test_frozen_weekly_window_boundaries_in_test_rules(at, allowed):
    assert scoring_open(at, qa_season()) is allowed


def test_normal_window_and_existing_snapshot_unchanged():
    normal = new_rules()
    qa = new_rules(test_mode=True)
    assert normal['start_weekday'] == 3 and normal['start_hour'] == 18 and not normal.get('test_mode')
    assert qa['test_mode'] is True and qa['start_weekday'] == 2 and qa['start_hour'] == 8
    normal_game = replace(qa_season(), scoring_rules=normal)
    assert not scoring_open(WEDNESDAY, normal_game)
    assert normal == new_rules()


def test_test_rules_window_uses_lobby_timezone_and_next_opening():
    game = qa_season('America/New_York')
    assert not scoring_open(WEDNESDAY, game)  # 03:00 in New York.
    opening = next_opening(WEDNESDAY, game)
    assert opening.hour == 8 and opening.weekday() == 2
    assert scoring_open(opening, game)


@pytest.mark.parametrize('days,hour', [(0, 0), (4, 18), (5, 10), (6, 23)])
def test_chug_duel_open_any_day_in_test_season_only(days, hour):
    game = qa_season()
    at = WEDNESDAY.replace(hour=hour) + timedelta(days=days)
    assert duel_open(at, game)
    assert not duel_open(at, replace(game, scoring_rules=new_rules()))


def test_chug_duel_in_test_season_stays_inside_season_bounds():
    game = qa_season()
    tick = timedelta(microseconds=1)
    assert not duel_open(game.starts_at - tick, game)
    assert duel_open(game.starts_at, game)
    assert duel_open(game.ends_at - tick, game)
    assert not duel_open(game.ends_at, game)


@pytest.mark.parametrize('days,hour', [(0, 0), (4, 18), (5, 10), (6, 23)])
def test_off_hours_checkin_scores_in_test_season_only(days, hour):
    game = qa_season()
    at = WEDNESDAY.replace(hour=hour) + timedelta(days=days)
    saved = create_scored_entry('member', game, 'beer', 'small', 'photo.jpg', INSIDE, 10,
        at, [TERRITORY], [], entry_id='capture')
    assert saved.points_awarded == 1
    assert saved.territory_id == TERRITORY.id
    with pytest.raises(CheckinRejected, match='scoring_closed'):
        create_scored_entry('member', replace(game, scoring_rules=new_rules()), 'beer', 'small',
            'photo.jpg', INSIDE, 10, at, [TERRITORY], [], entry_id='normal')


def test_test_checkin_requires_active_season_and_boolean_flag():
    game = qa_season()
    tick = timedelta(microseconds=1)
    assert not checkin_open(game.starts_at - tick, game)
    assert checkin_open(game.starts_at, game)
    assert checkin_open(game.ends_at - tick, game)
    assert not checkin_open(game.ends_at, game)
    game.scoring_rules['test_mode'] = 'true'
    assert not checkin_open(game.starts_at, game)


def test_rpc_receives_and_restores_frozen_test_rules(monkeypatch):
    game = qa_season()
    row = {'id':game.id, 'lobby_id':game.lobby_id, 'starts_at':game.starts_at.isoformat(),
           'ends_at':game.ends_at.isoformat(), 'length_choice':game.length_choice,
           'timezone_name':game.timezone_name, 'scoring_version':'v1', 'scoring_rules':game.scoring_rules}
    client = Mock()
    client.rpc.return_value.execute.return_value.data = [row]
    monkeypatch.setattr(db, 'get_client', lambda: client)
    monkeypatch.setattr(db, 'list_seasons_for_lobby', lambda _: [])
    restored = db.start_scoring_season('player', 'lobby', '1_month', 'Europe/Lisbon', test_mode=True)
    sent = client.rpc.call_args.args[1]['frozen_rules']
    assert sent == restored.scoring_rules == game.scoring_rules
    assert checkin_open(WEDNESDAY + timedelta(days=5), restored)
