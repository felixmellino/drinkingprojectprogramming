"""The shared empty-state card (theme.empty_state)."""
from streamlit.testing.v1 import AppTest

from theme import empty_state_html


def test_html_has_icon_title_and_line_escaped():
    html = empty_state_html("trophy", "No points <yet>", "First drink <b>wins</b>.")
    assert 'class="empty-state-icon"' in html and "mask-image" in html          # Phosphor icon as a mask
    assert "No points &lt;yet&gt;" in html and "&lt;b&gt;wins&lt;/b&gt;" in html
    assert "<b>wins</b>" not in html


def _app(check_in):
    return AppTest.from_string(f'''
import streamlit as st
from theme import empty_state
st.switch_page = lambda page: st.session_state.__setitem__("went_to", page)
empty_state("demo", "images", "No photos yet", "Every check-in adds one here.", check_in={check_in})
''').run()


def test_check_in_button_opens_the_camera_like_the_plus_tab():
    at = _app(True)
    assert not at.exception
    next(b for b in at.button if b.label == "Check in").click().run()
    assert at.session_state["checkin_open_camera"] is True
    assert at.session_state["went_to"] == "pages/3_Check_in.py"


def test_card_without_button():
    at = _app(False)
    assert not at.exception and not at.button
    assert any("No photos yet" in m.value for m in at.markdown)


def test_icon_is_scoped_to_its_own_card():
    html = empty_state_html("trophy", "x", "y", key="ranks")
    assert ".st-key-empty_state_ranks .empty-state-icon i{" in html
