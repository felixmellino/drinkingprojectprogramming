"""db.list_duel_results with a fake Supabase client (no network)."""
from unittest.mock import MagicMock

import pytest
from postgrest.exceptions import APIError

import data.db as db


@pytest.fixture
def client(monkeypatch):
    fake = MagicMock()
    tables = {}

    def table(name):
        query = MagicMock()
        query.select.return_value = query
        query.eq.return_value = query
        tables[name] = query
        return query
    fake.table.side_effect = table
    fake.tables = tables
    monkeypatch.setattr(db, "get_client", lambda: fake)
    return fake


def test_reads_completed_reaction_ids_and_won_time_duels(client):
    data = {
        "reaction_duels": [{"id": "r1"}],
        "time_duels": [
            {"id": "t1", "challenger_id": "a", "opponent_id": "b", "winner_id": "b",
             "finished_at": "2026-11-20T21:00:00+00:00"},
            {"id": "t2", "challenger_id": "a", "opponent_id": "b", "winner_id": None,
             "finished_at": "2026-11-20T22:00:00+00:00"}],
    }
    original = client.table.side_effect

    def table(name):
        query = original(name)
        query.execute.return_value.data = data[name]
        return query
    client.table.side_effect = table
    result = db.list_duel_results("season")
    assert result["reaction_ids"] == {"r1"}
    assert [row["id"] for row in result["time"]] == ["t1"], "only duels with a winner"
    assert result["time"][0]["finished_at"].isoformat() == "2026-11-20T21:00:00+00:00"
    for name in ("reaction_duels", "time_duels"):
        client.tables[name].eq.assert_any_call("season_id", "season")
        client.tables[name].eq.assert_any_call("status", "completed")


def test_missing_tables_read_as_no_duels(client):
    original = client.table.side_effect

    def table(name):
        query = original(name)
        query.execute.side_effect = APIError({"code": "42P01", "message": "missing"})
        return query
    client.table.side_effect = table
    assert db.list_duel_results("season") == {"reaction_ids": set(), "time": []}


def test_other_database_errors_are_raised(client):
    original = client.table.side_effect

    def table(name):
        query = original(name)
        query.execute.side_effect = APIError({"code": "500", "message": "down"})
        return query
    client.table.side_effect = table
    with pytest.raises(APIError):
        db.list_duel_results("season")
