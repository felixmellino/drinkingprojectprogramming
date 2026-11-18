"""Check displayed scoring results and access/error states through the real page."""
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

import data.db as db
from tests.test_checkins import TERRITORY
from tests.test_scoring_v1 import entry

ROOT = Path(__file__).resolve().parents[1]


def text(markup):
    class VisibleText(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts, self.in_style = [], False

        def handle_starttag(self, tag, attrs):
            if tag == "style":
                self.in_style = True

        def handle_endtag(self, tag):
            if tag == "style":
                self.in_style = False

        def handle_data(self, value):
            if not self.in_style:
                self.parts.append(value)
    parser = VisibleText()
    parser.feed(markup)
    return " ".join(" ".join(parser.parts).split())


@pytest.fixture
def ui(monkeypatch):
    state = {
        "entries": [entry("m1", "member", "beer", "large", 0),
                    entry("l1", "other", "shot", None, 1),
                    entry("m2", "member", "mixed", "medium", 2),
                    entry("l2", "other", "beer", "medium", 3),
                    entry("m3", "member", "wine", "medium", 4)],
        "players": [SimpleNamespace(id="mia", display_name="Mia", email="private@example.test"),
                    SimpleNamespace(id="leo", display_name="Leo")],
        "territories": [TERRITORY],
    }
    monkeypatch.setattr("shared.require_login", lambda: "mia")
    monkeypatch.setattr("shared.require_active_membership", lambda: ("member", "lobby", "season"))
    monkeypatch.setattr("shared.show_logged_in_as", lambda: None)
    monkeypatch.setattr("shared.get_territories", lambda: state["territories"])
    monkeypatch.setattr(db, "list_drink_entries", lambda _: state["entries"])
    monkeypatch.setattr(db, "list_memberships_for_lobby", lambda _: [
        SimpleNamespace(id="member", player_id="mia"), SimpleNamespace(id="other", player_id="leo")])
    monkeypatch.setattr(db, "list_players", lambda: state["players"])
    return state


def page():
    return AppTest.from_file(ROOT / "pages/4_Standings.py", default_timeout=10).run()


def all_markup(at):
    return "\n".join(item.value for item in at.markdown)


def board(at):
    return next(item.value for item in at.markdown if "<table" in item.value)


def test_display_keeps_exact_owner_income_and_base_territory_accounts(ui):
    at = page()
    assert not at.exception
    ranking = text(board(at))
    assert ranking.index("Mia") < ranking.index("Leo")
    assert "9.5 pts" in ranking and "6.75 pts" in ranking
    visible = text(all_markup(at))
    assert "Your rank #1" in visible and "Season points 9.5" in visible
    assert "Territories 1 Currently yours" in visible
    assert "8 pts" in visible and "6 pts" in visible
    assert "YOU" in ranking
    assert "private@example.test" not in all_markup(at)


def test_display_preserves_earliest_reached_tie_and_current_players_rank(ui):
    # Input deliberately lists Mia first, but Leo reached the tied total first.
    ui["entries"] = [entry("late", "member", "shot", None, 1, territory=None),
                     entry("early", "other", "shot", None, 0, territory=None)]
    at = page()
    assert not at.exception
    ranking = text(board(at))
    assert ranking.index("Leo") < ranking.index("Mia")
    assert "Your rank #2" in text(all_markup(at))


def test_empty_season_has_no_invented_rank_or_territory_owner(ui):
    ui["entries"] = []
    at = page()
    assert not at.exception
    assert any("No points logged yet" in item.value for item in at.info)
    visible = text(all_markup(at))
    assert "Your rank —" in visible and "Unclaimed" in visible
    assert "No owner yet" in visible
    assert not any("<table" in item.value for item in at.markdown)


@pytest.mark.parametrize("service", ["season", "territories"])
def test_service_failure_does_not_fabricate_zero_scores(ui, monkeypatch, service):
    def unavailable(*args):
        raise RuntimeError("Service unavailable")
    if service == "season":
        monkeypatch.setattr(db, "list_drink_entries", unavailable)
    else:
        monkeypatch.setattr("shared.get_territories", unavailable)
    at = page()
    assert not at.exception
    if service == "season":
        assert at.error
        assert not any("<table" in item.value for item in at.markdown)
    else:
        assert at.warning and "9.5 pts" in text(board(at))
        assert "Could not load" in text(all_markup(at))


def test_public_names_and_territory_names_are_rendered_as_text(ui):
    payload = '<img src=x onerror="alert(1)">'
    ui["players"][0].display_name = payload
    ui["territories"] = [replace(TERRITORY, name=payload)]
    at = page()
    assert not at.exception
    markup = all_markup(at)
    assert payload not in markup and "&lt;img" in markup


def test_whole_season_is_replayed_once_for_all_territory_cards(ui, monkeypatch):
    from unittest.mock import Mock
    from core.scoring_v1 import replay_season
    replay = Mock(wraps=replay_season)
    monkeypatch.setattr('core.scoring_v1.replay_season', replay)
    ui['territories'] = [TERRITORY] + [replace(TERRITORY,id=f'extra-{i}',name=f'Area {i}') for i in range(23)]
    at = page()
    assert not at.exception and '9.5 pts' in text(board(at))
    replay.assert_called_once()
