"""Season awards (R-S01 to R-S03): who wins each award, ties, legacy and empty seasons."""
from dataclasses import replace

from core.leaderboard import season_leaderboard
from core.models import SeasonTransfer
from core.season_recap import (CAPTURES, DRINKS, MVP, TAKEOVER, TERRITORIES, build_recap, csv_rows,
                               safe_cell)
from tests.test_scoring_v1 import START, entry

A, B = "territory-a", "territory-b"


def season_with_takeovers():
    """Mia claims A, Leo takes it (beats 3), Ana claims B, Mia retakes A (beats 4),
    Leo takes B from Ana (beats 5)."""
    return [entry("1", "mia", "beer", "large", 0, territory=A, order=1),
            entry("2", "leo", "shot", None, 1, territory=A, order=2),
            entry("3", "ana", "mixed", "large", 2, territory=B, order=3),
            entry("4", "mia", "mixed", "large", 3, territory=A, order=4),
            entry("5", "leo", "shot", None, 4, territory=B, order=5),
            entry("6", "leo", "shot", None, 5, territory=B, order=6)]


def award(recap, key):
    return next((a for a in recap.awards if a.key == key), None)


def test_awards_follow_the_same_replay_as_ranks():
    entries = season_with_takeovers()
    recap = build_recap(entries, me="mia")
    rows = season_leaderboard(entries)
    assert [s.competitor for s in recap.standings] == [c for c, _ in rows]
    assert award(recap, MVP).winner == rows[0][0]
    takeover = award(recap, TAKEOVER)
    assert (takeover.winner, takeover.loser, takeover.territory_id, takeover.value) == ("leo", "ana", B, 5)
    assert award(recap, DRINKS).winner == "leo" and award(recap, DRINKS).value == 3
    assert [a.key for a in recap.awards] == [MVP, TERRITORIES, TAKEOVER, CAPTURES, DRINKS]


def test_ties_go_to_the_better_final_rank():
    recap = build_recap(season_with_takeovers())
    # Mia and Leo each hold one territory and each gained two; the higher rank wins both.
    better = next(s.competitor for s in recap.standings if s.competitor in ("mia", "leo"))
    assert award(recap, TERRITORIES).winner == better and award(recap, TERRITORIES).value == 1
    assert award(recap, CAPTURES).winner == better and award(recap, CAPTURES).value == 2


def test_equal_takeovers_go_to_the_earlier_one():
    entries = [entry("1", "mia", "beer", "large", 0, territory=A, order=1),   # Mia 3 on A
               entry("2", "ana", "beer", "large", 1, territory=B, order=2),   # Ana 3 on B
               entry("3", "leo", "shot", None, 2, territory=A, order=3),      # beats Mia's 3
               entry("4", "ben", "shot", None, 3, territory=B, order=4)]      # beats Ana's 3, later
    assert award(build_recap(entries), TAKEOVER).winner == "leo"


def test_first_claims_count_as_captures_but_never_as_a_takeover():
    entries = [entry("1", "mia", "beer", "large", 0, territory=A, order=1),
               entry("2", "leo", "shot", None, 1, territory=B, order=2)]
    recap = build_recap(entries)
    assert award(recap, TAKEOVER) is None
    assert award(recap, CAPTURES).value == 1


def test_a_tie_in_a_territory_is_not_a_takeover():
    entries = [entry("1", "mia", "beer", "large", 0, territory=A, order=1),
               entry("2", "leo", "beer", "large", 1, territory=A, order=2)]
    assert award(build_recap(entries), TAKEOVER) is None


def test_duel_transfers_can_change_the_mvp():
    entries = [entry("1", "mia", "shot", None, 0, territory=None, order=1),
               entry("2", "leo", "beer", "large", 1, territory=None, order=2)]
    assert award(build_recap(entries), MVP).winner == "mia"
    stake = SeasonTransfer("t", "season", "mia", "leo", "mia", "leo", 3, 3, START)
    assert award(build_recap(entries, [stake]), MVP).winner == "leo"


def test_team_lobbies_award_teams():
    entries = [replace(e, team_id="red" if e.membership_id in ("mia", "ana") else "blue")
               for e in season_with_takeovers()]
    recap = build_recap(entries, me="red")
    assert {s.competitor for s in recap.standings} == {"red", "blue"}
    assert {a.winner for a in recap.awards} <= {"red", "blue"}
    assert recap.you.competitor == "red" and recap.you.drinks == 3


def test_legacy_season_has_no_territory_awards():
    entries = [replace(e, rule_version="legacy") for e in season_with_takeovers()]
    keys = [a.key for a in build_recap(entries).awards]
    assert keys == [MVP, DRINKS]


def test_empty_season_has_no_awards_and_no_viewer_line():
    recap = build_recap([], me="mia")
    assert recap.standings == [] and recap.awards == [] and recap.you is None and recap.podium == []


def test_rejected_entries_never_count():
    entries = [entry("1", "mia", "shot", None, 0, territory=A, order=1),
               replace(entry("2", "leo", "shot", None, 1, territory=A, order=2), location_check_result="uncertain")]
    recap = build_recap(entries)
    assert [s.competitor for s in recap.standings] == ["mia"] and award(recap, DRINKS).value == 1


def test_viewer_line_has_rank_points_and_counts():
    recap = build_recap(season_with_takeovers(), me="ana")
    assert recap.you.rank == 3 and recap.you.drinks == 1 and recap.you.territories == 0
    assert recap.you.captures == 1


def test_csv_matches_the_standings_and_blocks_formulas():
    recap = build_recap(season_with_takeovers())
    names = {"mia": "Mia", "leo": "=HYPERLINK(\"x\")", "ana": "Ana"}
    rows = csv_rows(recap, names)
    assert rows[0] == ["Rank", "Player", "Points", "Drinks", "Territories held", "Captures"]
    assert [r[0] for r in rows[1:]] == ["1", "2", "3"]
    assert all(not r[1].startswith("=") for r in rows[1:])
    assert safe_cell("+1") == "'+1" and safe_cell("@x") == "'@x" and safe_cell("Mia") == "Mia"
