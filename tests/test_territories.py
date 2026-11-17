from datetime import datetime

from core.models import DrinkEntry
from core.territories import replay_leader, territory_owner, territory_standings

TERRITORY_ID = "territory-a"


def make_entry(id_, membership_id, points, ts, territory_id=TERRITORY_ID, result="matched"):
    return DrinkEntry(
        id=id_,
        membership_id=membership_id,
        season_id="season-1",
        drink_type="shot",
        amount=None,
        photo_ref="photo",
        device_gps=None,
        photo_gps=None,
        territory_id=territory_id,
        location_check_result=result,
        points_awarded=points,
        submitted_at=ts,
    )


def test_replay_leader_tie_does_not_displace_current_leader():
    events = [
        (datetime(2026, 11, 19, 20, 0), "A", 10),
        (datetime(2026, 11, 19, 20, 5), "B", 10),  # ties A, A stays leader
    ]
    assert replay_leader(events) == "A"


def test_replay_leader_strict_overtake_flips_leader():
    events = [
        (datetime(2026, 11, 19, 20, 0), "A", 10),
        (datetime(2026, 11, 19, 20, 5), "B", 10),  # tie, A stays
        (datetime(2026, 11, 19, 20, 10), "B", 1),  # B now strictly ahead
    ]
    assert replay_leader(events) == "B"


def test_territory_owner_changes_hands_on_overtake():
    entries = [
        make_entry("e1", "A", 10, datetime(2026, 11, 19, 20, 0)),
        make_entry("e2", "B", 10, datetime(2026, 11, 19, 20, 5)),
    ]
    assert territory_owner(entries, TERRITORY_ID) == "A"  # tie -> A keeps it

    entries.append(make_entry("e3", "B", 1, datetime(2026, 11, 19, 20, 10)))
    assert territory_owner(entries, TERRITORY_ID) == "B"  # overtake -> B owns it


def test_only_matched_entries_count_toward_territory():
    entries = [
        make_entry("e1", "A", 10, datetime(2026, 11, 19, 20, 0)),
        make_entry("e2", "B", 100, datetime(2026, 11, 19, 20, 5), result="uncertain"),
    ]
    # B's entry is "uncertain", not "matched" -- doesn't count here.
    assert territory_owner(entries, TERRITORY_ID) == "A"


def test_territory_standings_sorted_descending():
    entries = [
        make_entry("e1", "A", 10, datetime(2026, 11, 19, 20, 0)),
        make_entry("e2", "B", 25, datetime(2026, 11, 19, 20, 5)),
    ]
    standings = territory_standings(entries, TERRITORY_ID)
    assert standings[0] == ("B", 25)
    assert standings[1] == ("A", 10)
