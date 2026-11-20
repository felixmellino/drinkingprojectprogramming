"""Dark mode: off by default, follows the browser's saved choice, switch in Profile."""
from streamlit.testing.v1 import AppTest


def _app(reader="None", switch="None", show_switch=False):
    """A page that loads the theme; the browser component is replaced by what it would send."""
    return AppTest.from_string(f'''
import streamlit as st
import theme
def fake(mode, **kwargs):
    st.session_state.setdefault("calls", []).append(mode)
    return {reader} if mode == "reader" else {switch}
theme._theme_switch = fake
theme.apply_theme()
if {show_switch}:
    theme.dark_mode_switch()
st.markdown("tokens:" + theme.component_tokens())
''')


def _css(at):
    return "".join(m.value for m in at.markdown)


def test_light_by_default_and_when_never_chosen():
    at = _app().run()
    assert not at.exception and "color-scheme: dark" not in _css(at)
    assert not at.session_state["calls"] == []          # the reader asked the browser
    assert "--bg: #0E1A24" not in _css(at)


def test_saved_dark_choice_turns_dark_mode_on():
    at = _app(reader='"dark"').run()
    assert not at.exception
    assert at.session_state["wego_dark_mode"] is True
    css = _css(at)
    assert "color-scheme: dark" in css and "--bg: #0E1A24" in css      # page and component tokens


def test_saved_light_choice_keeps_light():
    at = _app(reader='"light"').run()
    assert not at.exception and "color-scheme: dark" not in _css(at)


def test_switch_turns_dark_on_and_off():
    at = _app(switch='"dark"', show_switch=True).run()
    assert not at.exception and at.session_state["wego_dark_mode"] is True
    assert "switch" in at.session_state["calls"]
    off = _app(reader='"dark"', switch='"light"', show_switch=True).run()
    assert not off.exception and off.session_state["wego_dark_mode"] is False
