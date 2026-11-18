"""Navigation uses native page switches without dropping the signed-in identity."""
from pathlib import Path
from unittest.mock import Mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize("label,target", [
    ("Profile", "1_Profile.py"), ("Lobby", "2_Lobby.py"),
    ("Check in", "3_Check_in.py"), ("Map", "5_Map.py"), ("Leaderboard", "4_Standings.py"),
    ("Photo history", "6_Check_in_photos.py"),
    ("Minigames", "7_Minigames.py"),
])
def test_bottom_navigation_switches_to_the_requested_page(monkeypatch, label, target):
    switch = Mock()
    monkeypatch.setattr(st, "switch_page", switch)
    at = AppTest.from_string("from app_navigation import bottom_navigation\nbottom_navigation('leaderboard')").run()
    assert not at.exception
    assert [button.label for button in at.button] == ["Profile", "Lobby", "Check in", "Minigames", "Map", "Leaderboard", "Photo history"]
    at.session_state["player_id"] = "signed-in-player"
    next(button for button in at.button if button.label == label).click().run()
    assert not at.exception
    assert Path(switch.call_args.args[0]) == Path(__file__).resolve().parents[1] / "pages" / target
    assert at.session_state["player_id"] == "signed-in-player"
    assert ('checkin_open_camera' in at.session_state) is (label == 'Check in')
    if label == 'Check in':
        assert at.session_state['checkin_open_camera'] is True
