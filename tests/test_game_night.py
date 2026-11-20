"""Ranks tab, Game night view: which night, and who ranks where."""
from dataclasses import replace
from datetime import timedelta

from core.leaderboard import game_night_leaderboard, game_night_window
from tests.test_scoring_v1 import START, entry, season

# START is Thursday 19 Nov 2026, 18:00 Lisbon: the first game night opens then.


def test_window_is_the_running_game_night():
    start, end, current = game_night_window(START + timedelta(hours=3), season())
    assert (start, end, current) == (START, START + timedelta(days=3), True)


def test_between_game_nights_it_shows_the_last_one():
    monday = START + timedelta(days=4)
    start, end, current = game_night_window(monday, season())
    assert start == START and current is False


def test_before_the_first_game_night_there_is_none():
    assert game_night_window(START - timedelta(hours=1), season()) is None


def test_after_the_season_it_shows_its_last_game_night():
    s = season()
    start, _end, current = game_night_window(s.ends_at + timedelta(days=10), s)
    assert start < s.ends_at and current is False


def test_legacy_seasons_have_no_game_night_view():
    assert game_night_window(START, replace(season(), scoring_version="legacy")) is None


def test_only_drinks_of_that_night_count_and_everyone_is_listed():
    entries = [entry("a1", "ana", "beer", "large", 10),                 # 3, this night
               entry("b1", "ben", "shot", None, 20),                    # 4, this night
               entry("a2", "ana", "beer", "small", 60 * 24 * 7),        # next week: not counted
               replace(entry("c1", "cam", "wine", "large", 30), points_awarded=0)]   # zero: not counted
    rows = game_night_leaderboard(entries, ["ana", "ben", "cam", "dan"], START, START + timedelta(days=3))
    assert rows == [("ben", 4), ("ana", 3), ("cam", 0), ("dan", 0)]


def test_time_duel_bonus_counts_but_nothing_else_is_added():
    boosted = replace(entry("a1", "ana", "beer", "large", 10), time_bonus=0.75)
    rows = game_night_leaderboard([boosted], ["ana"], START, START + timedelta(days=3))
    assert rows == [("ana", 3.75)]


def test_ties_go_to_who_reached_the_total_first():
    entries = [entry("late", "ana", "beer", "large", 50, order=2),
               entry("early", "ben", "beer", "large", 5, order=1)]
    rows = game_night_leaderboard(entries, ["ana", "ben"], START, START + timedelta(days=3))
    assert [who for who, _ in rows] == ["ben", "ana"]
