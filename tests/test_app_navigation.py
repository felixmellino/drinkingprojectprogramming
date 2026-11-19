"""Navigation uses native page switches without dropping the signed-in identity."""
from pathlib import Path
from unittest.mock import Mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize("label,target", [
    ("Map", "5_Map.py"), ("Ranks", "4_Standings.py"), ("Check in", "3_Check_in.py"),
    ("Games", "7_Minigames.py"), ("Profile", "1_Profile.py"),
])
def test_bottom_navigation_switches_to_the_requested_page(monkeypatch, label, target):
    switch = Mock()
    monkeypatch.setattr(st, "switch_page", switch)
    at = AppTest.from_string("from app_navigation import bottom_navigation\nbottom_navigation('leaderboard')").run()
    assert not at.exception
    assert [button.label for button in at.button] == ["Map", "Ranks", "Check in", "Games", "Profile"]
    at.session_state["player_id"] = "signed-in-player"
    next(button for button in at.button if button.label == label).click().run()
    assert not at.exception
    assert Path(switch.call_args.args[0]) == Path(__file__).resolve().parents[1] / "pages" / target
    assert at.session_state["player_id"] == "signed-in-player"
    assert ('checkin_open_camera' in at.session_state) is (label == 'Check in')
    if label == 'Check in':
        assert at.session_state['checkin_open_camera'] is True


def test_check_in_plus_sits_in_the_middle_of_five_tabs():
    from app_navigation import DESTINATIONS
    assert len(DESTINATIONS) == 5
    assert DESTINATIONS[2][0] == "checkin"


def test_every_tab_icon_exists_in_outline_and_filled_form():
    from app_navigation import DESTINATIONS, icon_url
    for route, _label, _page, icon in DESTINATIONS:
        assert icon_url(icon).startswith("data:image/svg+xml;base64,")
        if route != "checkin":
            assert icon_url(f"{icon}-fill")


def test_lobby_and_photo_history_open_from_the_profile_menu(monkeypatch):
    switch = Mock()
    monkeypatch.setattr(st, "switch_page", switch)
    at = AppTest.from_string(
        "import streamlit as st\nfrom profile_ui import PAGES\n"
        "for key, label, page, icon in PAGES:\n"
        "    if st.button(label, key=key):\n"
        "        st.switch_page(page)").run()
    assert [b.label for b in at.button] == ["Lobbies", "Photo history"]
