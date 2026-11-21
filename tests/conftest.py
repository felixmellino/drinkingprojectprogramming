"""Shared test setup.

Every page now asks which season recaps the player has finished (the banner,
R-S03). Older tests mock only the reads they care about, so without this the
question would go to the real database whenever a local secrets file exists.
Default answer: nothing finished. Tests that need another answer patch it
themselves; tests/test_season_recap_db.py tests the real function.
"""
import pytest

import data.db as db


@pytest.fixture(autouse=True)
def no_finished_recaps(monkeypatch, request):
    if request.module.__name__.endswith("test_season_recap_db"):
        return
    monkeypatch.setattr(db, "finished_recap_seasons", lambda player_id: set())
