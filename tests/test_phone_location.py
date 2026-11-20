"""The Location switch in Profile, the follower on other pages and the session reading."""
import time
from pathlib import Path

from streamlit.testing.v1 import AppTest

FIX = {"lat": 38.6782, "lng": -9.3259, "accuracy_m": 15}


def run(monkeypatch, browser_reply, which="track_location"):
    monkeypatch.setattr("phone_location._phone_location", lambda **kwargs: browser_reply(kwargs))

    def page():
        import streamlit as st
        import phone_location
        getattr(phone_location, st.session_state["which"])()
        st.write(repr(phone_location.current_location()))

    at = AppTest.from_function(page)
    at.session_state["which"] = which
    return at.run()


def fresh():
    return dict(FIX, taken_at_ms=time.time() * 1000)


def test_follower_stores_the_reading_and_never_asks_for_permission_itself(monkeypatch):
    calls = []
    page = run(monkeypatch, lambda kwargs: calls.append(kwargs) or fresh())
    assert not page.exception
    assert "once" not in calls[0] and "mode" not in calls[0] and calls[0]["key"] == "live_location_tracker"
    assert "(38.6782, -9.3259), 15.0, None" in page.markdown[0].value


def test_switch_asks_through_the_visible_component_and_stores_the_reading(monkeypatch):
    calls = []
    page = run(monkeypatch, lambda kwargs: calls.append(kwargs) or fresh(), which="location_switch")
    assert not page.exception
    assert calls[0]["mode"] == "switch" and calls[0]["key"] == "location_switch"
    assert ":root" in calls[0]["tokens"]
    assert "(38.6782, -9.3259), 15.0, None" in page.markdown[0].value


def test_location_that_is_off_blocked_or_pending_is_reported_as_such(monkeypatch):
    for reply, expected in [({"error": "off"}, "'off'"), ({"error": "denied"}, "'denied'"), (None, "'waiting'")]:
        page = run(monkeypatch, lambda kwargs, reply=reply: reply)
        assert expected in page.markdown[0].value


def test_an_unknown_error_name_from_the_browser_is_invalid(monkeypatch):
    page = run(monkeypatch, lambda kwargs: {"error": "<script>"})
    assert "'invalid'" in page.markdown[0].value


def test_old_readings_are_stale(monkeypatch):
    page = run(monkeypatch, lambda kwargs: dict(FIX, taken_at_ms=time.time() * 1000 - 120_000))
    assert "'stale'" in page.markdown[0].value


def test_no_page_asks_for_location_on_its_own_after_login():
    """The browser prompt must only come from the tap on the Profile switch."""
    root = Path(__file__).resolve().parents[1]
    assert "ask_for_location" not in (root / "shared.py").read_text(encoding="utf-8")
    assert "ask_for_location" not in (root / "phone_location.py").read_text(encoding="utf-8")
    page = (root / "components" / "phone_location" / "index.html").read_text(encoding="utf-8")
    # The follower starts only after the on/off choice, and never while the browser would still ask.
    assert 'chosen() !== "on"' in page and 'state === "prompt"' in page
    # The switch's own geolocation call sits inside its click handler (a real tap).
    assert page.index('addEventListener("click"') < page.index("getCurrentPosition(position => {")
