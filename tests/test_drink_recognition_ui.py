"""The Check in page with the drink suggestion (R-C01), using the real Streamlit widgets."""
from unittest.mock import Mock

import pytest

import drink_recognition
from core.drink_recognition import LIMIT_REACHED, NO_DRINK, DrinkSuggestion
from tests.test_scoring_ui import button, open_checkin, radio, reward, set_location, ui  # noqa: F401 (fixture)


@pytest.fixture
def suggest(monkeypatch):
    """Switch the feature on with a fake suggest_drink; the real API is never called."""
    fake = Mock(return_value=DrinkSuggestion("wine", "large", "Looks like a large wine. Change it if that's wrong."))
    monkeypatch.setattr(drink_recognition, "api_key", lambda: "test-key")
    monkeypatch.setattr(drink_recognition, "suggest_drink", fake)
    return fake


def captions(page):
    return [item.value for item in page.caption]


def test_suggestion_preselects_drink_and_size_and_counts_after_submit(ui, suggest):
    state, _ = ui
    page = open_checkin()
    assert not page.exception
    assert radio(page, "Drink").value == "wine" and radio(page, "Size").value == "large"
    assert "Looks like a large wine. Change it if that's wrong." in captions(page)
    assert any("+4 points" in item.value for item in page.info)
    set_location(page, state)
    button(page, "Submit").click().run()
    assert not page.exception and 'reward-points">+4<' in reward(page)
    assert state["entries"][0].drink_type == "wine" and state["entries"][0].size == "large"


def test_player_can_overrule_the_suggestion(ui, suggest):
    state, _ = ui
    page = open_checkin()
    radio(page, "Drink").set_value("beer").run()
    radio(page, "Size").set_value("small").run()
    set_location(page, state)
    button(page, "Submit").click().run()
    assert state["entries"][0].drink_type == "beer" and state["entries"][0].points_awarded == 1


def test_claude_is_asked_once_per_photo_not_on_every_rerun(ui, suggest):
    state, _ = ui
    page = open_checkin()
    radio(page, "Size").set_value("medium").run()
    set_location(page, state)
    assert suggest.call_count == 1
    photo_bytes, rules = suggest.call_args.args
    assert photo_bytes == state["photo"].getvalue() and rules["version"] == "v1"
    assert suggest.call_args.kwargs == {"player_id": "player"}, "the limit counts per signed-in player"
    assert radio(page, "Size").value == "medium", "a rerun keeps the player's choice"


def test_retake_asks_again_for_the_new_photo(ui, suggest, monkeypatch):
    state, _ = ui
    monkeypatch.setattr("camera_capture.camera_photo", lambda key: state["photo"])
    page = open_checkin()
    assert suggest.call_count == 1
    suggest.return_value = DrinkSuggestion("shot", None, "Looks like a shot. Change it if that's wrong.")
    button(page, "Retake photo").click().run()
    assert not page.exception and suggest.call_count == 2
    assert radio(page, "Drink").value == "shot" and not any(item.label == "Size" for item in page.radio)


def test_failed_recognition_shows_the_normal_form_once(ui, suggest):
    state, _ = ui
    suggest.return_value = None
    page = open_checkin()
    set_location(page, state)
    assert suggest.call_count == 1, "a failure is remembered, not retried on every rerun"
    assert radio(page, "Drink").value == "beer" and radio(page, "Size").value == "small"
    assert not any("Looks like" in text or "Choose it yourself" in text for text in captions(page))
    button(page, "Submit").click().run()
    assert not page.exception and state["calls"] == 1


def test_no_drink_found_says_so_but_never_blocks_the_checkin(ui, suggest):
    state, _ = ui
    suggest.return_value = DrinkSuggestion(None, None, NO_DRINK)
    page = open_checkin()
    assert NO_DRINK in captions(page)
    assert radio(page, "Drink").value == "beer" and radio(page, "Size").value == "small"
    set_location(page, state)
    button(page, "Submit").click().run()
    assert not page.exception and state["calls"] == 1


def test_limit_message_is_shown_and_the_form_still_works(ui, suggest):
    state, _ = ui
    suggest.return_value = DrinkSuggestion(None, None, LIMIT_REACHED)
    page = open_checkin()
    assert LIMIT_REACHED in captions(page) and radio(page, "Drink").value == "beer"
    set_location(page, state)
    button(page, "Submit").click().run()
    assert not page.exception and state["calls"] == 1


def test_without_a_key_claude_is_never_asked(ui, monkeypatch):
    fake = Mock()
    monkeypatch.setattr(drink_recognition, "suggest_drink", fake)
    page = open_checkin()
    assert not page.exception and radio(page, "Drink").value == "beer"
    fake.assert_not_called()
