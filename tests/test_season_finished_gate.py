"""R-S03: a finished season's pages wait until the player watched the summary on Ranks."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

import data.db as db
import season_recap_ui
from tests.test_lobby_ui import ui  # noqa: F401  (fixture)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def finished(ui, monkeypatch):
    """The current lobby is 'Finished lobby'; its season has ended. Watched seasons live in state."""
    state = {"watched": set(), "reads": 0}

    def history(player_id):
        state["reads"] += 1
        return set(state["watched"])
    monkeypatch.setattr(db, "finished_recap_seasons", history)

    def context(player_id, membership_id, lobby_id, season_id):
        member = next((m for m in ui['members'] if m.id == membership_id and m.lobby_id == lobby_id), None)
        season = next((s for s in ui['seasons'].get(lobby_id, []) if s.id == season_id), None)
        return (member, season) if member else (None, None)
    monkeypatch.setattr(db, 'membership_context', context)
    state["season"] = ui['seasons']['past'][0]
    return state


def open_page(path, ui):
    at = AppTest.from_file(ROOT / path, default_timeout=10)
    season = ui['seasons']['past'][0]
    for key, value in dict(player_id='me', current_membership_id='m-past', current_lobby_id='past',
                           current_lobby_name='Finished lobby', current_season_id=season.id).items():
        at.session_state[key] = value
    return at.run()


def season(ends_in):
    return SimpleNamespace(id="s", ends_at=datetime.now(timezone.utc) + ends_in)


@pytest.mark.parametrize("ends_in, watched, due", [
    (timedelta(minutes=5), set(), False),      # still running: nothing to watch
    (timedelta(0), set(), True),               # now == ends_at counts as ended (R-R03)
    (-timedelta(days=1), set(), True),
    (-timedelta(days=1), {"s"}, False),        # watched earlier, on any device
    (-timedelta(days=1), None, False),         # history unreadable: never hold players back
])
def test_summary_pending_rule(monkeypatch, ends_in, watched, due):
    import streamlit as st
    monkeypatch.setattr(st, "session_state", {})
    monkeypatch.setattr(season_recap_ui, "finished_or_empty", lambda pid: watched)
    clock = Mock(wraps=datetime)
    now = datetime.now(timezone.utc)
    clock.now.return_value = now
    monkeypatch.setattr(season_recap_ui, "datetime", clock)
    assert season_recap_ui.summary_pending("me", SimpleNamespace(id="s", ends_at=now + ends_in)) is due


def test_a_watched_season_is_remembered_without_another_read(monkeypatch):
    import streamlit as st
    monkeypatch.setattr(st, "session_state", {})
    reads = Mock(return_value={"s"})
    monkeypatch.setattr(season_recap_ui, "finished_or_empty", reads)
    ended = season(-timedelta(hours=1))
    assert not season_recap_ui.summary_pending("me", ended)
    assert not season_recap_ui.summary_pending("me", ended)
    assert reads.call_count == 1
    assert season_recap_ui.summary_pending("someone-else", ended) is False and reads.call_count == 2


@pytest.mark.parametrize("path", ["pages/5_Map.py", "pages/3_Check_in.py", "pages/7_Minigames.py",
                                  "pages/8_Activity.py", "pages/6_Check_in_photos.py"])
def test_other_pages_send_the_player_to_ranks(ui, finished, monkeypatch, path):
    entries = Mock(return_value=[])
    monkeypatch.setattr(db, 'list_drink_entries', entries)
    at = open_page(path, ui)
    assert not at.exception
    assert any('season is finished' in i.value for i in at.info)
    assert at.button(key='season_finished_go_to_ranks').label == 'Go to Ranks'
    entries.assert_not_called()  # nothing of the season loads behind the notice


def test_ranks_shows_only_watch_summary_and_opens_the_story(ui, finished, monkeypatch):
    entries = Mock(return_value=[])
    monkeypatch.setattr(db, 'list_drink_entries', entries)
    opened = Mock()
    monkeypatch.setattr(season_recap_ui, 'open_recap', opened)
    at = open_page('pages/4_Standings.py', ui)
    assert not at.exception
    assert any('The season is finished' in m.value for m in at.markdown)
    entries.assert_not_called()
    at.button(key='season_finished_watch').click().run()
    opened.assert_called_once_with('past', 'Finished lobby', finished["season"].id, animate=True,
                                   return_to=season_recap_ui.RANKS_PAGE)


def test_after_watching_ranks_and_the_map_open_again(ui, finished, monkeypatch):
    finished["watched"].add(finished["season"].id)
    at = open_page('pages/4_Standings.py', ui)
    assert not at.exception
    assert not any(b.key == 'season_finished_watch' for b in at.button)
    assert any('Final standings' in c.value for c in at.caption)


def test_a_running_season_is_never_held_back(ui, finished):
    at = AppTest.from_file(ROOT / 'pages/4_Standings.py', default_timeout=10)
    season = ui['seasons']['new'][0]
    for key, value in dict(player_id='me', current_membership_id='m-new', current_lobby_id='new',
                           current_lobby_name='Newest lobby', current_season_id=season.id).items():
        at.session_state[key] = value
    at.run()
    assert not at.exception and not any(b.key == 'season_finished_watch' for b in at.button)
    assert finished["reads"] == 0  # no history read while the season runs
