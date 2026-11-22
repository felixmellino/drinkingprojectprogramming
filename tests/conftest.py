"""Shared test setup.

Past lobby cards read the player's recap history (R-S03). Stub the read so
UI tests do not contact the real database when local secrets exist.
Default answer: nothing finished. Tests that need another answer patch it
themselves; tests/test_season_recap_db.py tests the real function.
"""
import pytest

import data.db as db
import drink_recognition


@pytest.fixture(autouse=True)
def no_real_drink_recognition(monkeypatch):
    """Tests never call the real Claude API, even when a local secrets file has a key.

    Tests that need the suggestion patch drink_recognition themselves.
    """
    monkeypatch.setattr(drink_recognition, "api_key", lambda: None)


@pytest.fixture(autouse=True)
def no_finished_recaps(monkeypatch, request):
    if request.module.__name__.endswith("test_season_recap_db"):
        return
    monkeypatch.setattr(db, "finished_recap_seasons", lambda player_id: set())


@pytest.fixture(autouse=True)
def fresh_private_bucket_checks():
    """The private-bucket check is remembered per server process; each test starts fresh."""
    db._private_bucket_checked_at.clear()
    yield
    db._private_bucket_checked_at.clear()


@pytest.fixture(autouse=True)
def no_real_picture_access(monkeypatch, request):
    """Lobby and Map start the picture permission check early. Pages tested with a
    credential would otherwise send it to a real database when a local secrets
    file exists. Default: no friendships. tests/test_profile_picture_db.py tests
    the real function."""
    if request.module.__name__.endswith("test_profile_picture_db"):
        return
    monkeypatch.setattr(db, "profile_picture_access", lambda viewer_id, credential_version: [])


@pytest.fixture(autouse=True)
def no_real_duel_results(monkeypatch, request):
    """The Activity feed reads duel results; keep pages that don't mock it off the network."""
    if request.module.__name__.endswith("test_duel_results_db"):
        return
    monkeypatch.setattr(db, "list_duel_results", lambda season_id: {"reaction_ids": set(), "time": []})
