"""Drink suggestion from the check-in photo (R-C01).

No test calls the real Anthropic API: a fake client stands in for it, and
tests/conftest.py switches the feature off everywhere else.
"""
import base64
import json
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import anthropic
import httpx2
import pytest
import streamlit
from PIL import Image

import drink_recognition
from core.drink_recognition import (ANSWER_SCHEMA, DRINKS, LIMIT_PER_HOUR, LIMIT_REACHED, LIMIT_WINDOW_SECONDS, NO_DRINK,
                                    SIZES, UNSURE, DrinkSuggestion, prompt_for, suggestion_from_answer, within_limit)
from core.scoring_v1 import DRINK_LABELS, SIZE_LABELS, rules_for
from tests.test_scoring_v1 import season


@pytest.fixture(autouse=True)
def fresh_limit(monkeypatch):
    """Every test starts with no recent recognitions and a clock it controls."""
    clock = [1000.0]
    monkeypatch.setattr(drink_recognition, "_calls", {})
    monkeypatch.setattr(drink_recognition, "_clock", lambda: clock[0])
    return clock


def answer(**changes):
    base = {"drink_visible": True, "several_drinks": False, "drink": "beer", "drink_confidence": "high",
            "size": "large", "size_confidence": "high"}
    return {**base, **changes}


def jpeg(width=12, height=6):
    output = BytesIO()
    Image.new("RGB", (width, height), "orange").save(output, "JPEG")
    return output.getvalue()


# --- Rules: what the form preselects -------------------------------------------------------------


def test_confident_answer_preselects_drink_and_size():
    assert suggestion_from_answer(answer()) == DrinkSuggestion(
        "beer", "large", "Looks like a large beer. Change it if that's wrong.")


def test_medium_confidence_is_still_enough_to_preselect():
    result = suggestion_from_answer(answer(drink="wine", drink_confidence="medium", size="small",
                                           size_confidence="medium"))
    assert (result.drink, result.size) == ("wine", "small")


def test_mixed_drink_uses_its_label():
    assert suggestion_from_answer(answer(drink="mixed", size="medium")).message.startswith(
        "Looks like a medium mixed drink.")


def test_shot_never_preselects_a_size():
    assert suggestion_from_answer(answer(drink="shot", size="large")) == DrinkSuggestion(
        "shot", None, "Looks like a shot. Change it if that's wrong.")


@pytest.mark.parametrize("changes", [{"size_confidence": "low"}, {"size": "none"}])
def test_unsure_size_preselects_only_the_drink(changes):
    assert suggestion_from_answer(answer(**changes)) == DrinkSuggestion("beer", None, "Looks like beer. Check the size.")


@pytest.mark.parametrize("changes", [{"drink_confidence": "low"}, {"several_drinks": True}, {"drink": "unknown"}])
def test_unsure_drink_preselects_nothing(changes):
    assert suggestion_from_answer(answer(**changes)) == DrinkSuggestion(None, None, UNSURE)


def test_no_drink_in_the_photo_preselects_nothing():
    assert suggestion_from_answer(answer(drink_visible=False)) == DrinkSuggestion(None, None, NO_DRINK)


@pytest.mark.parametrize("bad", [
    None, "beer", [], {},
    {k: v for k, v in answer().items() if k != "size"},  # missing field
    {**answer(), "points": 99},                          # extra field
    answer(drink="cider"), answer(size="huge"), answer(drink_confidence="certain"),
    answer(size_confidence=None), answer(drink_visible="yes"), answer(several_drinks=1),
])
def test_malformed_answer_gives_no_suggestion(bad):
    assert suggestion_from_answer(bad) is None


def test_schema_uses_the_scoring_rules_drinks_and_sizes():
    """Drinks and sizes come from one place: the scoring rules."""
    assert DRINKS == tuple(DRINK_LABELS) and SIZES == tuple(SIZE_LABELS)
    assert ANSWER_SCHEMA["properties"]["drink"]["enum"] == [*DRINK_LABELS, "unknown"]
    assert set(ANSWER_SCHEMA["required"]) == set(ANSWER_SCHEMA["properties"])
    assert ANSWER_SCHEMA["additionalProperties"] is False


def test_prompt_lists_the_seasons_volumes():
    text = prompt_for(rules_for(season()))
    assert "small 250 ml, medium 330 ml, large 500 ml" in text
    assert "small 100 ml, medium 150 ml, large 250 ml" in text
    assert "500 ml" not in prompt_for({"volumes": {"beer": {"large": 568}}})


# --- API call with a fake client ------------------------------------------------------------------


class FakeClient:
    """Stands in for anthropic.Anthropic: records the request and returns or raises."""

    def __init__(self, reply=None, error=None):
        self.requests = []
        self.reply, self.error = reply, error
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.reply


def reply(text, stop_reason="end_turn"):
    blocks = [SimpleNamespace(type="thinking", thinking="")]
    if text is not None:
        blocks.append(SimpleNamespace(type="text", text=text))
    return SimpleNamespace(stop_reason=stop_reason, content=blocks)


def test_suggestion_from_a_successful_call():
    client = FakeClient(reply(json.dumps(answer())))
    result = drink_recognition.suggest_drink(jpeg(), rules_for(season()), player_id="p1", client=client)
    assert (result.drink, result.size) == ("beer", "large")
    request = client.requests[0]
    assert request["model"] == "claude-opus-5-5"
    assert request["output_config"]["format"] == {"type": "json_schema", "schema": ANSWER_SCHEMA}
    assert request["fallbacks"] == "default" and request["betas"] == ["server-side-fallback-2026-07-01"]
    image, text = request["messages"][0]["content"]
    assert image["source"]["media_type"] == "image/jpeg" and "250 ml" in text["text"]


def test_photo_is_shrunk_before_sending():
    client = FakeClient(reply(json.dumps(answer())))
    drink_recognition.suggest_drink(jpeg(3000, 1500), player_id="p1", client=client)
    sent = base64.b64decode(client.requests[0]["messages"][0]["content"][0]["source"]["data"])
    with Image.open(BytesIO(sent)) as image:
        assert image.format == "JPEG" and image.size == (1024, 512)


def test_small_photo_keeps_its_size():
    with Image.open(BytesIO(drink_recognition.shrink_photo(jpeg(800, 600)))) as image:
        assert image.size == (800, 600)


def make_request():
    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.mark.parametrize("error", [
    anthropic.APIConnectionError(request=make_request()),
    anthropic.APITimeoutError(request=make_request()),
    anthropic.RateLimitError("busy", response=httpx2.Response(429, request=make_request()), body=None),
    anthropic.AuthenticationError("bad key", response=httpx2.Response(401, request=make_request()), body=None),
    anthropic.InternalServerError("down", response=httpx2.Response(500, request=make_request()), body=None),
])
def test_api_failures_give_no_suggestion(error):
    assert drink_recognition.suggest_drink(jpeg(), player_id="p1", client=FakeClient(error=error)) is None


@pytest.mark.parametrize("response", [
    reply(json.dumps(answer()), stop_reason="refusal"),
    reply('{"drink_visible": true', stop_reason="max_tokens"),
    reply("not json"),
    reply(None),
    reply(json.dumps({"drink": "beer"})),
])
def test_unusable_answers_give_no_suggestion(response):
    assert drink_recognition.suggest_drink(jpeg(), player_id="p1", client=FakeClient(response)) is None


def test_unreadable_photo_gives_no_suggestion_and_no_call():
    client = FakeClient(reply(json.dumps(answer())))
    assert drink_recognition.suggest_drink(b"not a jpeg", player_id="p1", client=client) is None
    assert client.requests == []


def test_without_a_key_nothing_is_sent(monkeypatch):
    monkeypatch.setattr(anthropic, "Anthropic", Mock(side_effect=AssertionError("must not build a client")))
    assert drink_recognition.suggest_drink(jpeg(), player_id="p1") is None


def test_with_a_key_the_client_gives_up_quickly(monkeypatch):
    built = {}

    def fake_anthropic(**options):
        built.update(options)
        return FakeClient(reply(json.dumps(answer())))

    monkeypatch.setattr(drink_recognition, "api_key", lambda: "test-key")
    monkeypatch.setattr(anthropic, "Anthropic", fake_anthropic)
    assert drink_recognition.suggest_drink(jpeg(), player_id="p1").drink == "beer"
    assert built == {"api_key": "test-key", "timeout": 12, "max_retries": 0}


def test_key_comes_from_secrets_first_then_environment(monkeypatch):
    monkeypatch.undo()  # use the real api_key(), not the conftest switch-off
    monkeypatch.setattr(streamlit, "secrets", {})
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert drink_recognition.api_key() is None and not drink_recognition.is_enabled()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    assert drink_recognition.api_key() == "from-env"
    monkeypatch.setattr(streamlit, "secrets", {"ANTHROPIC_API_KEY": "from-secrets"})
    assert drink_recognition.api_key() == "from-secrets" and drink_recognition.is_enabled()


# --- Limit: at most 10 recognitions per player per rolling hour ----------------------------------


def test_limit_boundaries():
    now = 10_000.0
    assert LIMIT_PER_HOUR == 10 and LIMIT_WINDOW_SECONDS == 3600
    assert within_limit([now - 1] * 9, now)[0], "the 10th call is allowed"
    assert not within_limit([now - 1] * 10, now)[0], "the 11th call is not"
    allowed, kept = within_limit([now - 3600] + [now - 3599] * 9, now)
    assert allowed and len(kept) == 9, "a call exactly one hour old no longer counts"


def test_eleventh_photo_in_an_hour_is_not_sent(fresh_limit):
    client = FakeClient(reply(json.dumps(answer())))
    for _ in range(10):
        assert drink_recognition.suggest_drink(jpeg(), player_id="p1", client=client).drink == "beer"
    assert drink_recognition.suggest_drink(jpeg(), player_id="p1", client=client) == DrinkSuggestion(
        None, None, LIMIT_REACHED)
    assert len(client.requests) == 10
    # Another player has their own allowance.
    assert drink_recognition.suggest_drink(jpeg(), player_id="p2", client=client).drink == "beer"
    # One hour after the first call, one slot is free again.
    fresh_limit[0] += 3600
    assert drink_recognition.suggest_drink(jpeg(), player_id="p1", client=client).drink == "beer"
    assert len(client.requests) == 12


def test_failed_calls_also_count_towards_the_limit():
    """A timeout still costs an API request, so it uses a slot."""
    client = FakeClient(error=anthropic.APITimeoutError(request=make_request()))
    for _ in range(10):
        assert drink_recognition.suggest_drink(jpeg(), player_id="p1", client=client) is None
    assert drink_recognition.suggest_drink(jpeg(), player_id="p1", client=client).message == LIMIT_REACHED


def test_unreadable_photo_does_not_use_a_slot():
    client = FakeClient(reply(json.dumps(answer())))
    for _ in range(12):
        drink_recognition.suggest_drink(b"not a jpeg", player_id="p1", client=client)
    assert drink_recognition._calls == {} and client.requests == []
