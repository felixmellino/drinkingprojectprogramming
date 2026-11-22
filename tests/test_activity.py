"""Activity feed events: which drinks and captures appear, in which order."""
from dataclasses import replace
from datetime import timedelta

from core.activity import CAPTURE, CHECKIN, MEDAL, activity_events, with_promotions
from core.medals import Promotion
from core.scoring_v1 import corrected_entry, replay_season
from tests.test_scoring_v1 import START, entry, season

A = "territory-a"


def kinds(events):
    return [(event.kind, event.member) for event in events]


def test_empty_season_has_no_events():
    assert activity_events([]) == []


def test_first_drink_in_a_free_territory_is_a_checkin_and_a_capture():
    events = activity_events([entry("1", "Mia", "beer", "large", 0)])
    assert kinds(events) == [(CAPTURE, "Mia"), (CHECKIN, "Mia")]
    capture, checkin = events
    assert capture.territory_id == A and capture.previous_owner is None and capture.competitor == "Mia"
    assert checkin.points == 3 and checkin.drink_type == "beer" and checkin.size == "large"


def test_overtake_names_new_and_previous_owner_newest_first():
    events = activity_events([entry("1", "Mia", "beer", "large", 0),   # Mia 3
                              entry("2", "Leo", "shot", None, 1)])     # Leo 4 > 3
    assert kinds(events) == [(CAPTURE, "Leo"), (CHECKIN, "Leo"), (CAPTURE, "Mia"), (CHECKIN, "Mia")]
    assert events[0].previous_owner == "Mia" and events[0].entry_id == "2"


def test_tie_does_not_capture_r_r01():
    events = activity_events([entry("1", "Mia", "beer", "large", 0),   # 3
                              entry("2", "Leo", "beer", "large", 1)])  # 3, tie keeps Mia
    assert kinds(events) == [(CHECKIN, "Leo"), (CAPTURE, "Mia"), (CHECKIN, "Mia")]


def test_owner_adding_points_is_not_a_new_capture():
    events = activity_events([entry("1", "Mia", "beer", "large", 0), entry("2", "Mia", "shot", None, 3)])
    assert [event.kind for event in events] == [CHECKIN, CAPTURE, CHECKIN]


def test_outside_checkin_appears_without_territory_or_capture():
    events = activity_events([entry("1", "Mia", "shot", None, 0, territory=None)])
    assert kinds(events) == [(CHECKIN, "Mia")]
    assert events[0].territory_id is None and events[0].points == 4


def test_rejected_uncertain_and_zero_point_entries_never_appear():
    uncertain = replace(entry("1", "Mia", "shot", None, 0), location_check_result="uncertain")
    zero = replace(entry("2", "Leo", "shot", None, 1), points_awarded=0)
    assert activity_events([uncertain, zero]) == []


def test_correction_that_undoes_a_lead_removes_the_capture():
    events = [entry("1", "Mia", "beer", "large", 0), entry("2", "Leo", "shot", None, 1)]
    assert any(e.kind == CAPTURE and e.competitor == "Leo" for e in activity_events(events))
    events[1] = corrected_entry(events[1], season(), "beer", "small", START + timedelta(minutes=2))
    after = activity_events(events)
    assert not any(e.kind == CAPTURE and e.competitor == "Leo" for e in after)
    assert after[0].points == 1  # the corrected drink is shown, not the original


def test_team_mode_capture_belongs_to_the_team_and_names_the_drinker():
    first = replace(entry("1", "Mia", "beer", "large", 0), team_id="Red")
    second = replace(entry("2", "Leo", "shot", None, 1), team_id="Blue")
    events = activity_events([first, second])
    assert (events[0].kind, events[0].competitor, events[0].previous_owner, events[0].member) == \
        (CAPTURE, "Blue", "Red", "Leo")


def test_event_order_not_input_order_decides_the_feed():
    first = entry("z", "first", "shot", None, 0, order=1)
    second = entry("a", "second", "shot", None, 0, order=2)
    assert kinds(activity_events([second, first]))[-1] == (CHECKIN, "first")


def test_captures_match_the_replay_ownership():
    events = [entry("1", "Mia", "beer", "large", 0), entry("2", "Leo", "shot", None, 1),
              entry("3", "Mia", "mixed", "medium", 2), entry("4", "Leo", "beer", "medium", 3)]
    replay = replay_season(events)
    feed = [e for e in activity_events(events) if e.kind == CAPTURE]
    assert feed[0].competitor == replay.owners[A]  # newest capture = current owner
    assert [(c[0], c[2], c[3]) for c in replay.captures] == [("1", "Mia", None), ("2", "Leo", "Mia"), ("3", "Mia", "Leo")]
    # What each capture beat: nothing (free), Mia's 3, then Leo's 4.
    assert [c[4] for c in replay.captures] == [0, 3, 4]


def test_medals_slot_in_by_time_without_reordering_the_replay():
    """A capture stays directly above the check-in that caused it, even when the
    saved timestamps disagree with the replay order (event_order)."""
    late_order = replace(entry("1", "Mia", "beer", "large", 5), event_order=1)  # saved first, stamped later
    early_order = replace(entry("2", "Leo", "shot", None, 0), event_order=2)    # takes the territory
    events = activity_events([late_order, early_order])
    medal = Promotion("Mia", START + timedelta(minutes=10), ("Beginner in drinks",))
    merged = with_promotions(events, [medal])
    assert merged[0].kind == MEDAL
    assert [(e.kind, e.entry_id) for e in merged[1:]] == [(e.kind, e.entry_id) for e in events]
    assert [e.kind for e in merged[1:3]] == [CAPTURE, CHECKIN] and merged[1].entry_id == merged[2].entry_id


def test_a_medal_at_the_same_moment_goes_above_the_checkin():
    events = activity_events([entry("1", "Mia", "beer", "large", 0, territory=None)])
    merged = with_promotions(events, [Promotion("Mia", START, ("Beginner in drinks",))])
    assert [e.kind for e in merged] == [MEDAL, CHECKIN]


# --- Duel results (Chug: from the two linked drinks; Quiz/Reaction: stake ledger; Time: boost) -------

from datetime import datetime, timezone  # noqa: E402

from core.activity import (CHUG_DUEL, DUEL, QUIZ_DUEL, REACTION_DUEL, TIME_DUEL,  # noqa: E402
                           TIME_DUEL_PRIZE)
from core.models import SeasonTransfer  # noqa: E402


def chug(winner="Felix", loser="Ben", *, decided=True, territory=A, minute=5):
    """Two linked small beers (1 point each); the loser's entry names the winner."""
    a = replace(entry("w", winner, "beer", "small", minute, territory=territory, order=10), duel_id="d1")
    b = replace(entry("l", loser, "beer", "small", minute, territory=territory, order=11), duel_id="d1")
    if decided:
        b = replace(b, duel_transfer_to=winner, duel_transfer_order=12)
    return a, b


def test_finished_chug_duel_is_one_row_with_both_drinks_points_for_the_winner():
    events = activity_events([*chug(territory=None)])
    assert kinds(events) == [(DUEL, "Felix")]
    duel = events[0]
    assert duel.game == CHUG_DUEL and duel.points == 2, "the winner gets both drinks' base points"
    assert duel.loser_member == "Ben" and duel.loser == "Ben" and duel.lost_points == 1


def test_chug_duel_without_a_winner_stays_two_checkins():
    events = activity_events([*chug(decided=False, territory=None)])
    assert [event.kind for event in events] == [CHECKIN, CHECKIN]
    assert {event.points for event in events} == {1}


def test_capture_by_a_chug_duel_is_shown_directly_above_its_result():
    """Felix's duel drink claims the free territory; the banner sits on the duel row."""
    events = activity_events([*chug(minute=5)])
    assert [(e.kind, e.competitor) for e in events] == [(CAPTURE, "Felix"), (DUEL, "Felix")]


def test_earlier_drinks_stay_below_the_duel():
    events = activity_events([entry("x", "Mia", "beer", "small", 0, order=1), *chug(minute=5)])
    assert [e.kind for e in events] == [DUEL, CAPTURE, CHECKIN]
    assert events[1].competitor == events[2].member == "Mia"


def transfer(id_, winner, loser, points, minute):
    return SeasonTransfer(id_, "season", loser, winner, loser, winner, points, 100 + minute,
                          START + timedelta(minutes=minute))


def test_stake_duels_say_which_game_and_how_much_changed_hands():
    events = activity_events([entry("1", "Mia", "beer", "small", 0, territory=None, order=1)],
                             [transfer("quiz-1", "Mia", "Leo", 5, 10), transfer("react-1", "Leo", "Mia", 3, 20)],
                             {"reaction_ids": {"react-1"}, "time": []})
    assert [(e.kind, e.game) for e in events] == [(DUEL, REACTION_DUEL), (DUEL, QUIZ_DUEL), (CHECKIN, None)]
    reaction, quiz, _ = events
    assert (reaction.member, reaction.loser_member, reaction.points, reaction.lost_points) == ("Leo", "Mia", 3, 3)
    assert (quiz.member, quiz.loser_member, quiz.points) == ("Mia", "Leo", 5)


def test_stake_duels_are_called_duel_when_the_game_is_unknown():
    events = activity_events([], [transfer("t", "Mia", "Leo", 4, 1)], None)
    assert [(e.kind, e.game) for e in events] == [(DUEL, "Duel")]


def test_time_duel_win_shows_the_boost_and_no_points_lost():
    won = {"id": "t1", "challenger_id": "Leo", "opponent_id": "Mia", "winner_id": "Mia",
           "finished_at": START + timedelta(minutes=30)}
    events = activity_events([], (), {"reaction_ids": set(), "time": [won]})
    duel, = events
    assert (duel.game, duel.member, duel.loser_member, duel.prize, duel.lost_points) == \
        (TIME_DUEL, "Mia", "Leo", TIME_DUEL_PRIZE, 0)


def test_timed_duel_at_the_same_moment_as_a_drink_goes_above_it():
    events = activity_events([entry("1", "Mia", "beer", "small", 10, territory=None, order=1)],
                             [transfer("q", "Mia", "Leo", 3, 10)], {"reaction_ids": set(), "time": []})
    assert [e.kind for e in events] == [DUEL, CHECKIN]
