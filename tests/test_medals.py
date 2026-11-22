from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from core.medals import lobby_promotions, medal_cards, rank_index
from core.models import LobbyMembership, SeasonTransfer
from core.profile_stats import ProfileStats
from tests.test_scoring_v1 import START, entry, season


def test_rank_thresholds_and_top_rank_progress():
    cards = list(medal_cards(ProfileStats(Decimal("99.75"), 35, 20, 5)))
    assert cards == [
        ("Total points", Decimal("99.75"), 4, 100),
        ("Drinks", 35, 5, 60),
        ("Lobbies played", 20, 7, None),
        ("Total Wins", 5, 5, 8),
    ]
    assert rank_index("points", 100) == 5
    assert rank_index("points", -1) == 0


def test_lifetime_baseline_promotes_in_source_lobby_and_wins_at_season_end():
    first = replace(season(), id="first", lobby_id="old", ends_at=START + timedelta(minutes=1))
    second = replace(season(), ends_at=START + timedelta(minutes=10))
    early = replace(entry("early", "old-member", "mixed", "large", 0), season_id=first.id)
    new = entry("new", "member", "mixed", "large", 5)
    members = [LobbyMembership("old-member", "player", "old", first.starts_at),
               LobbyMembership("member", "player", "lobby", second.starts_at)]
    history = [(first, [early], []), (second, [new, new], [])]
    cutoff = START + timedelta(minutes=2)

    assert lobby_promotions("old", members, history, launched_at=cutoff, now=second.ends_at) == []
    posts = lobby_promotions("lobby", members, history, launched_at=cutoff, now=second.ends_at)
    assert [(post.at, post.medals) for post in posts] == [
        (new.submitted_at, ("Regular in total points", "Regular in lobbies played")),
        (second.ends_at, ("Regular in total wins",)),
    ]
    before_end = second.ends_at - timedelta(microseconds=1)
    assert lobby_promotions("lobby", members, history, launched_at=cutoff, now=before_end) == posts[:1]


def test_recovered_points_do_not_repeat_a_promotion_and_rejected_drinks_do_not_count():
    game = season()
    member = LobbyMembership("member", "player", "lobby", game.starts_at)
    first = entry("first", member.id, "mixed", "large", 0)
    second = entry("second", member.id, "mixed", "large", 3)
    third = entry("third", member.id, "mixed", "large", 6)
    rejected = replace(third, id="rejected", location_check_result="uncertain", points_awarded=100)
    loss = SeasonTransfer("loss", game.id, member.id, "other", member.id, "other", 5, 20,
                          START + timedelta(minutes=4))
    posts = lobby_promotions("lobby", [member], [(game, [first, second, third, rejected], [loss])],
                             launched_at=START, now=START + timedelta(minutes=10))
    assert [post.medals for post in posts] == [
        ("Beginner in total points", "Beginner in drinks", "Beginner in lobbies played"),
        ("Regular in total points",),
    ]
