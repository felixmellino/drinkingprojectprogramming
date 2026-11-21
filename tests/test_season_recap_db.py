"""Finishing a season recap (R-S03): who may, when, and that it is saved once."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import data.db as db
from core.models import Season

NOW = datetime.now(timezone.utc)


@pytest.fixture
def store(monkeypatch):
    rows = {}

    class Query:
        def __init__(self):
            self.player = None

        def select(self, fields):
            assert fields == "season_id"
            return self

        def eq(self, field, value):
            assert field == "player_id"
            self.player = value
            return self

        def upsert(self, payload, on_conflict):
            assert on_conflict == "player_id,season_id"
            rows[(payload["player_id"], payload["season_id"])] = payload
            return self

        def execute(self):
            return SimpleNamespace(data=[{"season_id": s} for p, s in rows if p == self.player])

    class Client:
        def table(self, name):
            assert name == "season_recap_views"
            return Query()

    ends = {"over": NOW - timedelta(hours=1), "running": NOW + timedelta(days=3)}
    monkeypatch.setattr(db, "get_client", Client)
    monkeypatch.setattr(db, "get_season", lambda sid: Season(sid, "lobby", NOW - timedelta(days=30), ends[sid],
                                                               "1_month") if sid in ends else None)
    monkeypatch.setattr(db, "list_memberships_for_player", lambda pid, include_left=False:
                        [SimpleNamespace(id="m", lobby_id="lobby")] if pid in ("me", "left") else [])
    return rows


def test_a_player_finishes_an_ended_season_once(store):
    assert db.finished_recap_seasons("me") == set()
    db.finish_season_recap("me", "over")
    db.finish_season_recap("me", "over")  # a second Close changes nothing
    assert db.finished_recap_seasons("me") == {"over"} and len(store) == 1
    assert db.finished_recap_seasons("someone-else") == set()


def test_a_player_who_never_played_is_refused(store):
    with pytest.raises(PermissionError):
        db.finish_season_recap("stranger", "over")
    with pytest.raises(PermissionError):
        db.finish_season_recap("me", "missing-season")
    assert not store


def test_a_running_season_cannot_be_finished_early(store):
    with pytest.raises(ValueError, match="still running"):
        db.finish_season_recap("me", "running")
    assert not store


def test_access_asks_for_memberships_including_players_who_left(store, monkeypatch):
    seen = {}

    def memberships(pid, include_left=False):
        seen["include_left"] = include_left
        return [SimpleNamespace(id="m", lobby_id="lobby")]
    monkeypatch.setattr(db, "list_memberships_for_player", memberships)
    season, membership = db.recap_access("left", "over")
    assert season.id == "over" and membership.id == "m" and seen["include_left"] is True
