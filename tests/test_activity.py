"""Activity feed events: which drinks and captures appear, in which order."""
from dataclasses import replace
from datetime import timedelta

from core.activity import CAPTURE, CHECKIN, activity_events
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
