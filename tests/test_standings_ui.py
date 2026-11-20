"""Check displayed scoring results and access/error states through the real page."""
import re
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
    monkeypatch.setattr(db, 'list_season_transfers', lambda _: [])
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
    monkeypatch.setattr(db, "list_memberships_for_lobby", lambda _, **kwargs: [
        SimpleNamespace(id="member", player_id="mia"), SimpleNamespace(id="other", player_id="leo")])
    monkeypatch.setattr(db, "list_public_usernames", lambda: [dict(id=p.id,display_name=p.display_name) for p in state['players']])
    return state


def page():
    at = AppTest.from_file(ROOT / "pages/4_Standings.py", default_timeout=10)
    at.session_state["current_membership_id"] = "member"
    at.session_state["current_season_id"] = "season"
    return at.run()


def all_markup(at):
    return "\n".join(item.value for item in at.markdown)


def rank_of(markup, name):
    """The rank a player/team is actually labelled with, regardless of the
    podium's visual DOM order (2nd, 1st, 3rd left-to-right). The current
    """
    for m in re.finditer(r'<div class="standings-podium-place standings-podium-(\d)">(.*?)</span></span></div>', markup, re.S):
        if name in text(m.group(2)):
            return int(m.group(1))
    for offset, m in enumerate(re.finditer(r'<div class="standings-row[^"]*">(.*?)</div>', markup, re.S)):
        if name in text(m.group(1)):
            return offset + 4
    return None


def test_display_keeps_exact_owner_income_and_base_territory_accounts(ui):
    at = page()
    assert not at.exception
    markup = all_markup(at)
    assert rank_of(markup, "Mia") == 1
    assert rank_of(markup, "Leo") == 2
    visible = text(markup)
    assert "9.5" in visible and "6.75" in visible
    assert "YOU" in visible
    assert 'title="Yours"' in markup
    assert "private@example.test" not in markup


def test_display_preserves_earliest_reached_tie_and_current_players_rank(ui):
    # Input deliberately lists Mia first, but Leo reached the tied total first.
    ui["entries"] = [entry("late", "member", "shot", None, 1, territory=None),
                     entry("early", "other", "shot", None, 0, territory=None)]
    at = page()
    assert not at.exception
    markup = all_markup(at)
    assert rank_of(markup, "Leo") == 1
    assert rank_of(markup, "Mia") == 2


def test_empty_season_has_no_invented_rank_or_territory_owner(ui):
    ui["entries"] = []
    at = page()
    assert not at.exception
    assert any("No points logged yet" in item.value for item in at.info)
    markup = all_markup(at)
    assert 'title="Unclaimed"' in markup
    assert '<ol class="standings-podium"' not in markup and '<li class="standings-row' not in markup


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
    markup = all_markup(at)
    if service == "season":
        assert at.error
        assert '<ol class="standings-podium"' not in markup and '<li class="standings-row' not in markup
    else:
        assert at.warning
        assert rank_of(markup, "Mia") == 1
        assert '<div class="standings-pills"' not in markup


def test_public_names_and_territory_names_are_rendered_as_text(ui):
    payload = '<img src=x onerror="alert(1)">'
    ui["players"][0].display_name = payload
    ui["territories"] = [replace(TERRITORY, name=payload)]
    at = page()
    assert not at.exception
    markup = all_markup(at)
    assert payload not in markup and "&lt;img" in markup


def test_whole_season_is_replayed_once_for_all_territory_pills(ui, monkeypatch):
    from unittest.mock import Mock
    from core.scoring_v1 import replay_season
    replay = Mock(wraps=replay_season)
    monkeypatch.setattr('core.scoring_v1.replay_season', replay)
    ui['territories'] = [TERRITORY] + [replace(TERRITORY,id=f'extra-{i}',name=f'Area {i}') for i in range(23)]
    at = page()
    assert not at.exception
    assert rank_of(all_markup(at), "Mia") == 1
    replay.assert_called_once()


def test_departed_player_keeps_rank_and_quiz_transfers(ui, monkeypatch):
    """The merge must retain both historical membership names and quiz stakes."""
    from core.models import SeasonTransfer
    from tests.test_scoring_v1 import START

    ui['entries'] = [entry('a', 'member', 'mixed', 'large', 0, order=1, territory=None),
                     entry('b', 'other', 'mixed', 'large', 1, order=2, territory=None)]
    transfer = SeasonTransfer('quiz', 'season', 'member', 'other', 'member', 'other', 3, 3, START)
    monkeypatch.setattr(db, 'list_season_transfers', lambda _: [transfer])
    def memberships(lobby_id, *, include_left=False):
        assert lobby_id == 'lobby'
        current = SimpleNamespace(id='member', player_id='mia', left_at=None)
        departed = SimpleNamespace(id='other', player_id='leo', left_at=START)
        return [current, departed] if include_left else [current]
    monkeypatch.setattr(db, 'list_memberships_for_lobby', memberships)
    at = page()
    assert not at.exception
    markup = all_markup(at)
    assert rank_of(markup, 'Leo') == 1
    assert rank_of(markup, 'Mia') == 2
    assert '<span class="standings-podium-points">8</span>' in markup
    assert '<span class="standings-podium-points">2</span>' in markup


# Tie tag: rows arrive ranked, ties earliest-first.
import standings_ui  # noqa: E402
from standings_ui import reached_first  # noqa: E402

TIE_NAMES = {"a": "Ana", "b": "Tomás", "c": "Ben", "d": "Dana"}


def test_reached_first_only_on_upper_of_equal_neighbours():
    rows = [("a", 9), ("b", 8), ("c", 8)]
    assert [reached_first(rows, i) for i in range(3)] == [False, True, False]


def test_leaderboard_renders_tie_tag_and_medal_podium(monkeypatch):
    shown = []
    monkeypatch.setattr(standings_ui.st, "markdown", lambda markup, **_: shown.append(markup))
    standings_ui.leaderboard([("a", 9), ("b", 8), ("c", 8), ("d", 5)], TIE_NAMES, "d")
    markup = "".join(shown)
    assert markup.count("standings-first-tag") == 1
    assert "pts behind" not in markup and "standings-gap" not in markup
    for colour in ("var(--accent)", "var(--medal-2)", "var(--medal-3)"):
        assert f"background:{colour};" in markup
        assert f"0 0 0 6px {colour};" in markup               # avatar ringed in its step's colour
    from photo_history_ui import identity_colour
    assert f"background:{identity_colour({'membership_id': 'a'})};color:#fff;" in markup  # own colour


# -- Player sheet (tap a place on Ranks) -------------------------------------
from datetime import timedelta  # noqa: E402
from tests.test_scoring_v1 import START  # noqa: E402


def test_player_stats_count_scored_drinks_territories_favourite_and_last():
    entries = [entry("1", "m", "beer", "large", 0), entry("2", "m", "beer", "small", 5),
               entry("3", "m", "shot", None, 9, territory=None),           # outside the map, latest
               entry("4", "x", "wine", "large", 10),
               replace(entry("5", "m", "wine", "large", 11), points_awarded=0)]  # zero points: not counted
    stats = standings_ui.player_stats("m", entries, {"territory-a": "m", "b": "x"}, {"territory-a": "Bairro Alto"})
    assert stats["drinks"] == 3 and stats["territories"] == 1 and stats["favourite"] == "Beer"
    assert stats["last_place"] == "Outside the map" and stats["last_at"] == START + timedelta(minutes=9)
    matched = standings_ui.player_stats("x", entries, None, {"territory-a": "Bairro Alto"})
    assert matched["last_place"] == "Bairro Alto" and matched["territories"] is None   # territories unavailable


def test_player_stats_for_someone_without_drinks():
    stats = standings_ui.player_stats("nobody", [entry("1", "m", "beer", "large", 0)], {}, {})
    assert stats == {"drinks": 0, "territories": 0, "favourite": None, "last_place": None, "last_at": None}


def test_ago_reads_like_a_phone():
    now = START + timedelta(days=3)
    assert standings_ui.ago(now, now) == "just now"
    assert standings_ui.ago(now - timedelta(minutes=22), now) == "22 min ago"
    assert standings_ui.ago(now - timedelta(hours=5), now) == "5 h ago"
    assert standings_ui.ago(START, now) == f"{START:%a %d %b}"


def test_player_sheet_html_shows_four_tiles_escaped():
    stats = {"drinks": 9, "territories": None, "favourite": None, "last_place": "<b>Pub</b>",
             "last_at": START}
    html = standings_ui.player_sheet_html("LucasStink", 1, 16.75, stats, START + timedelta(minutes=22))
    assert "Rank 1 · 16.75 points" in html and html.count('class="sheet-stat"') == 4
    assert "<b>Pub</b>" not in html and "&lt;b&gt;Pub&lt;/b&gt;" in html and "22 min ago" in html
    assert html.count(">—<") == 2                       # territories unavailable, no favourite


def test_tapping_a_place_opens_that_players_sheet(ui):
    at = page()
    assert not at.exception
    tap = next(b for b in at.button if b.label == "Show Leo's profile")
    tap.click().run()
    assert not at.exception
    sheet = "".join(m.value for m in at.markdown if "sheet-grid" in m.value)
    assert "Rank 2" in sheet and sheet.count('class="sheet-stat"') == 4
