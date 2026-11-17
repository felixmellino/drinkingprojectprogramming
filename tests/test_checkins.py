from datetime import datetime, timedelta

import pytest

from core.checkins import CheckinRejected, create_drink_entry
from core.models import Territory

TERRITORY = Territory(
    id="territory-a",
    name="Bairro Alto",
    boundary={
        "type": "Polygon",
        "coordinates": [
            [[-9.15, 38.70], [-9.14, 38.70], [-9.14, 38.71], [-9.15, 38.71], [-9.15, 38.70]]
        ],
    },
)
INSIDE = (38.705, -9.145)
OUTSIDE = (38.80, -9.00)
# 2026-11-19 is a Thursday, inside the game window (starts 12:00).
IN_WINDOW_TS = datetime(2026, 11, 19, 20, 0, 0)
OUTSIDE_WINDOW_TS = datetime(2026, 11, 17, 20, 0, 0)  # a Tuesday


def test_valid_check_in_scores_full_points():
    entry = create_drink_entry(
        "membership-1", "season-1", "beer", 2, "photo-1", INSIDE, None, IN_WINDOW_TS, [TERRITORY], []
    )
    assert entry.points_awarded > 0
    assert entry.location_check_result == "matched"
    assert entry.territory_id == TERRITORY.id


def test_missing_photo_is_rejected():
    with pytest.raises(CheckinRejected) as exc:
        create_drink_entry("membership-1", "season-1", "beer", 2, "", INSIDE, None, IN_WINDOW_TS, [TERRITORY], [])
    assert exc.value.reason == "missing_photo"


def test_missing_amount_for_beer_is_rejected():
    with pytest.raises(CheckinRejected) as exc:
        create_drink_entry(
            "membership-1", "season-1", "beer", None, "photo-1", INSIDE, None, IN_WINDOW_TS, [TERRITORY], []
        )
    assert exc.value.reason == "missing_amount"


def test_duplicate_within_window_is_rejected():
    first = create_drink_entry(
        "membership-1", "season-1", "beer", 1, "photo-1", INSIDE, None, IN_WINDOW_TS, [TERRITORY], []
    )
    second_ts = IN_WINDOW_TS + timedelta(minutes=1)
    with pytest.raises(CheckinRejected) as exc:
        create_drink_entry(
            "membership-1", "season-1", "beer", 1, "photo-2", INSIDE, None, second_ts, [TERRITORY], [first]
        )
    assert exc.value.reason == "duplicate_check_in"


def test_same_drink_after_window_is_allowed():
    first = create_drink_entry(
        "membership-1", "season-1", "beer", 1, "photo-1", INSIDE, None, IN_WINDOW_TS, [TERRITORY], []
    )
    later_ts = IN_WINDOW_TS + timedelta(minutes=5)
    second = create_drink_entry(
        "membership-1", "season-1", "beer", 1, "photo-2", INSIDE, None, later_ts, [TERRITORY], [first]
    )
    assert second.points_awarded > 0


def test_different_drink_type_within_window_is_allowed():
    first = create_drink_entry(
        "membership-1", "season-1", "beer", 1, "photo-1", INSIDE, None, IN_WINDOW_TS, [TERRITORY], []
    )
    second_ts = IN_WINDOW_TS + timedelta(seconds=30)
    second = create_drink_entry(
        "membership-1", "season-1", "wine", 1, "photo-2", INSIDE, None, second_ts, [TERRITORY], [first]
    )
    assert second.points_awarded > 0


def test_outside_every_territory_still_scores_total_points():
    entry = create_drink_entry(
        "membership-1", "season-1", "shot", None, "photo-1", OUTSIDE, None, IN_WINDOW_TS, [TERRITORY], []
    )
    assert entry.points_awarded > 0
    assert entry.territory_id is None
    assert entry.location_check_result == "outside"


def test_outside_game_window_scores_zero_but_does_not_raise():
    entry = create_drink_entry(
        "membership-1", "season-1", "shot", None, "photo-1", INSIDE, None, OUTSIDE_WINDOW_TS, [TERRITORY], []
    )
    assert entry.points_awarded == 0


def test_unavailable_location_scores_zero():
    entry = create_drink_entry(
        "membership-1", "season-1", "shot", None, "photo-1", None, None, IN_WINDOW_TS, [TERRITORY], []
    )
    assert entry.points_awarded == 0
    assert entry.location_check_result == "unavailable"
