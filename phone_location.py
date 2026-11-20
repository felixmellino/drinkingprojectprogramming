"""Phone location for the Check-in and Map pages (R-L01, R-L04).

location_switch() is the Location switch in Profile: a tap asks the browser for
permission. track_location() mounts an invisible browser component that follows
the phone's GPS while the page is open (only when the switch is on) and keeps
the newest reading in this session only. current_location() returns that reading after checking it
(core/location.py's parse_phone_reading): valid numbers, accuracy, age.
Nothing here is written to the database.
"""

import time
from pathlib import Path

import streamlit as st
from streamlit.components.v1 import declare_component

from core.location import parse_phone_reading

_phone_location = declare_component(
    "phone_location", path=str(Path(__file__).parent / "components" / "phone_location")
)

_READING_KEY = "live_location_reading"


def _tokens() -> str:
    css = (Path(__file__).parent / "assets" / "theme.css").read_text(encoding="utf-8")
    return css[css.index(":root {"):css.index("/* Base */")]


def track_location() -> None:
    """Follow the phone's position on this page, but only if the player turned
    Location on in Profile and the browser still allows it. This never opens a
    permission prompt by itself (the switch does, from a tap), so the browser's
    question no longer appears at random moments. Otherwise the reading says "off"."""
    value = _phone_location(key="live_location_tracker", default=None)
    if value is not None:
        st.session_state[_READING_KEY] = value


def location_switch(*, compact: bool = False, follow: bool = False) -> None:
    """The visible Location switch. Turning it on asks the browser for permission straight
    away; the choice is remembered in this browser and shared by every switch.
    compact: the small pill for the Map's top bar. follow: the switch also follows the
    position while it is on (the Map uses it instead of the invisible follower)."""
    value = _phone_location(mode="switch", compact=compact, follow=follow, tokens=_tokens(),
                            key="location_switch_map" if compact else "location_switch", default=None)
    if value is not None:
        st.session_state[_READING_KEY] = value


def current_location():
    """(device_gps, accuracy_m, problem) for the newest reading in this
    session; problem is None when the reading can be used."""
    return parse_phone_reading(st.session_state.get(_READING_KEY), now_ms=time.time() * 1000)
