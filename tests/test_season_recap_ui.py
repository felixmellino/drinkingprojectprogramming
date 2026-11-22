"""Season recap screens: wording, the recap page's access checks and Close, the banner
and the Lobby buttons (R-S01 to R-S03)."""
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import data.db as db
import season_recap_ui
from core.models import Season
from core.season_recap import build_recap
from tests.test_scoring_v1 import START
from tests.test_season_recap import season_with_takeovers

ROOT = Path(__file__).resolve().parents[1]
NAMES = {"mia": "Mia", "leo": "Leo", "ana": "Ana"}
TERRITORIES = {"territory-a": "Bairro Alto", "territory-b": "Shortys"}
ENDED = Season("season", "lobby", START - timedelta(days=30), START + timedelta(days=1), "1_month")


def payload(me="ana"):
    return season_recap_ui.recap_payload(build_recap(season_with_takeovers(), me=me), names=NAMES,
                                         territory_names=TERRITORIES, me=me, lobby_name="Bairro Nights",
                                         season=ENDED)


def test_award_words_name_players_territories_and_the_viewer():
    data = payload(me="ana")
    awards = {a["key"]: a for a in data["awards"]}
    assert awards["takeover"]["winner"] == "Leo"
    assert awards["takeover"]["detail"] == "Took Shortys from you, who had 5 points there"
    assert awards["drinks"]["detail"] == "3 drinks"
    assert awards["territories"]["detail"] == "1 territory at the end"
    assert data["you"]["headline"].startswith("You finished 3rd with ")
    assert data["you"]["detail"] == "1 drink, 0 territories held, 1 capture"
    assert data["dates"] == "20 Oct to 20 Nov 2026" and data["lobby"] == "Bairro Nights"
    assert [p["place"] for p in data["podium"]] == [1, 2, 3]
    assert set(data["icons"]) >= {"mvp", "takeover", "you"}


def test_a_viewer_who_never_scored_gets_a_kind_line():
    assert payload(me="ben")["you"]["headline"] == "You didn't score this season"


def test_ordinals():
    assert [season_recap_ui.ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 101)] == \
        ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "101st"]


def test_banner_lists_only_recent_unfinished_ended_seasons():
    now = START + timedelta(days=5)
    def row(lobby, ends):
        return (SimpleNamespace(id=lobby, name=lobby.title()), None,
                Season(f"s-{lobby}", lobby, ends - timedelta(days=7), ends, "1_week"))
    rows = [row("newer", now - timedelta(days=1)), row("older", now - timedelta(days=3)),
            row("done", now - timedelta(days=2)), row("ancient", now - timedelta(days=40)),
            row("running", now + timedelta(days=2))]
    assert season_recap_ui.unfinished_recaps(rows, {"s-done"}, now) == [
        ("older", "Older", "s-older"), ("newer", "Newer", "s-newer")]


# The recap page --------------------------------------------------------------

@pytest.fixture
def page_env(monkeypatch):
    state = {"value": None, "access": lambda pid, sid: (ENDED, SimpleNamespace(id="mia", team_id=None))}
    monkeypatch.setattr("shared.require_login", lambda: "player-mia")
    monkeypatch.setattr("shared.show_logged_in_as", lambda: None)
    monkeypatch.setattr("shared.get_territories", lambda: [SimpleNamespace(id=k, name=v) for k, v in TERRITORIES.items()])
    monkeypatch.setattr(db, "recap_access", lambda pid, sid: state["access"](pid, sid))
    monkeypatch.setattr(db, "list_drink_entries", lambda sid: season_with_takeovers())
    monkeypatch.setattr(db, "list_season_transfers", lambda sid: [])
    monkeypatch.setattr(db, "list_memberships_for_lobby", lambda lid, **kw: [
        SimpleNamespace(id=m, player_id=f"player-{m}") for m in NAMES])
    monkeypatch.setattr(db, "list_public_usernames", lambda: [dict(id=f"player-{m}", display_name=n) for m, n in NAMES.items()])
    state["finish"] = Mock()
    monkeypatch.setattr(db, "finish_season_recap", state["finish"])
    state["board"] = Mock(side_effect=lambda payload, **kw: state["value"])
    monkeypatch.setattr(season_recap_ui, "board", state["board"])
    state["switch"] = Mock()
    monkeypatch.setattr(st, "switch_page", state["switch"])
    return state


def open_page(**session):
    at = AppTest.from_file(ROOT / "pages/9_Season_recap.py", default_timeout=10)
    at.session_state["_recap_season_id"] = "season"
    at.session_state["_recap_lobby_name"] = "Bairro Nights"
    for key, value in session.items():
        at.session_state[key] = value
    return at.run()


def test_first_open_plays_the_story_with_the_final_standings(page_env):
    at = open_page(_recap_animate=True, _recap_opened="t1")
    assert not at.exception
    args, kwargs = page_env["board"].call_args
    assert kwargs["animate"] is True and kwargs["opened"] == "t1"
    assert [a["key"] for a in args[0]["awards"]] == ["mvp", "territories", "takeover", "captures", "drinks"]
    page_env["finish"].assert_not_called()


def test_close_saves_once_and_returns_to_the_lobby(page_env):
    page_env["value"] = {"action": "close", "opened": "t1"}
    at = open_page(_recap_animate=True, _recap_opened="t1",
                   _unfinished_recaps=[("lobby", "Bairro Nights", "season"), ("x", "X", "other")])
    assert not at.exception
    page_env["finish"].assert_called_once_with("player-mia", "season")
    assert at.session_state["_unfinished_recaps"] == [("x", "X", "other")]
    assert page_env["switch"].call_args.args[0] == "pages/2_Lobby.py"


def test_a_close_from_an_earlier_visit_is_ignored(page_env):
    page_env["value"] = {"action": "close", "opened": "old"}
    open_page(_recap_opened="new")
    page_env["finish"].assert_not_called()


def test_a_stranger_sees_no_season_data(page_env):
    def refuse(pid, sid):
        raise PermissionError("no")
    page_env["access"] = refuse
    at = open_page()
    assert at.error and "season you played in" in at.error[0].value
    page_env["board"].assert_not_called()


def test_a_running_season_has_no_awards_yet(page_env):
    def running(pid, sid):
        raise ValueError("This season is still running.")
    page_env["access"] = running
    at = open_page()
    assert "still running" in at.info[0].value
    page_env["board"].assert_not_called()


def test_without_a_chosen_season_the_page_points_to_the_lobby(page_env):
    at = AppTest.from_file(ROOT / "pages/9_Season_recap.py", default_timeout=10).run()
    assert "Lobby page" in at.info[0].value and any(b.label == "Open Lobby" for b in at.button)


def test_a_database_failure_shows_an_error(page_env, monkeypatch):
    def down(sid):
        raise RuntimeError("Service unavailable")
    monkeypatch.setattr(db, "list_drink_entries", down)
    at = open_page()
    assert not at.exception and at.error
    page_env["board"].assert_not_called()


def test_csv_download_has_the_standings(page_env):
    at = open_page()
    download = at.get("download_button")[0]
    assert download.proto.label == "Download standings (CSV)"
    text = season_recap_ui.csv_text(build_recap(season_with_takeovers()), NAMES)
    assert text.splitlines()[0] == "Rank,Player,Points,Drinks,Territories held,Captures"
    assert len(text.splitlines()) == 4


# Banner and Lobby buttons -----------------------------------------------------

def banner_page():
    import streamlit as st
    import season_recap_ui
    season_recap_ui.banner()
    st.write("page body")


def test_banner_opens_the_oldest_unfinished_season(monkeypatch):
    switch = Mock()
    monkeypatch.setattr(st, "switch_page", switch)
    at = AppTest.from_function(banner_page)
    at.session_state["_unfinished_recaps"] = [("lobby", "Bairro <Nights>", "season"), ("x", "X", "other")]
    at.run()
    assert any("Your season in Bairro &lt;Nights&gt; is over." in m.value for m in at.markdown)
    at.button(key="season_recap_banner_open").click().run()
    assert switch.call_args.args[0] == season_recap_ui.RECAP_PAGE
    assert at.session_state["_recap_season_id"] == "season" and at.session_state["_recap_animate"] is True


def test_no_banner_once_everything_is_finished():
    at = AppTest.from_function(banner_page)
    at.session_state["_unfinished_recaps"] = []
    at.run()
    assert not at.button and not any("is over" in m.value for m in at.markdown)


def lobby_page():
    import streamlit as st
    from types import SimpleNamespace
    import season_recap_ui
    season_recap_ui.lobby_button(SimpleNamespace(id="lobby", name="Bairro Nights"),
                                 SimpleNamespace(id="season"), st.session_state["finished"])


@pytest.mark.parametrize("finished,label,animate", [
    (set(), "Finish season", True), ({"season"}, "Season awards", False), (None, "Season awards", False)])
def test_past_lobby_button_follows_whether_the_season_is_finished(monkeypatch, finished, label, animate):
    monkeypatch.setattr(st, "switch_page", Mock())
    at = AppTest.from_function(lobby_page)
    at.session_state["finished"] = finished
    at.run()
    assert at.button[0].label == label
    at.button[0].click().run()
    assert at.session_state["_recap_animate"] is animate
