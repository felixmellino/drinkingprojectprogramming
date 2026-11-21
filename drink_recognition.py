"""Server-only Claude call that suggests the drink in a check-in photo.

This is the only file that talks to the Anthropic API. The feature is off
unless ANTHROPIC_API_KEY is set in the Streamlit secrets or the environment.
Any failure (no key, network, timeout, refusal, odd answer) returns None, and
the Check in page then shows the normal form: a suggestion never blocks a
check-in and never changes points.
"""
import base64
import json
import logging
import os
import threading
import time
from io import BytesIO

import anthropic
from PIL import Image

from core.drink_recognition import (ANSWER_SCHEMA, LIMIT_REACHED, DrinkSuggestion, prompt_for, suggestion_from_answer,
                                    within_limit)

log = logging.getLogger(__name__)
if not log.handlers:
    # Streamlit Cloud shows stderr under Manage app -> Logs. Without a handler
    # only warnings would appear there; the answer summary is logged as info.
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(_handler)
    log.setLevel(logging.INFO)

MODEL = "claude-opus-5-5"
MAX_SIDE_PX = 1024      # smaller image: fewer tokens, faster answer, still enough detail
TIMEOUT_SECONDS = 12    # the player waits on the form, so give up quickly
MAX_TOKENS = 4000       # covers the model's short reasoning plus the small JSON answer

# Recent call times per player, kept in this server process like the login
# throttle's dummy-check limit: it resets when the app restarts.
_calls: dict[str, list[float]] = {}
_calls_lock = threading.Lock()   # Streamlit serves sessions on several threads
_clock = time.monotonic


def take_slot(player_id: str) -> bool:
    """Count one recognition for the player; False when the hourly limit is used up."""
    now = _clock()
    with _calls_lock:
        allowed, kept = within_limit(_calls.get(player_id, []), now)
        if allowed:
            kept.append(now)
        if kept:
            _calls[player_id] = kept
        else:
            _calls.pop(player_id, None)
        return allowed


def api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    try:
        import streamlit as st
        key = st.secrets.get("ANTHROPIC_API_KEY") or key
    except FileNotFoundError:
        pass
    return key or None


def is_enabled() -> bool:
    return api_key() is not None


def shrink_photo(jpeg: bytes) -> bytes:
    """Scale the (already metadata-free) check-in JPEG down to MAX_SIDE_PX."""
    with Image.open(BytesIO(jpeg), formats=("JPEG",)) as image:
        image = image.convert("RGB")
        image.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX))
        output = BytesIO()
        image.save(output, format="JPEG", quality=85)
    return output.getvalue()


def suggest_drink(jpeg: bytes, rules: dict | None = None, *, player_id: str, client=None) -> DrinkSuggestion | None:
    """Ask Claude which drink and size the photo shows. None means: no suggestion."""
    if client is None:
        key = api_key()
        if key is None:
            log.info("Drink recognition is off: no ANTHROPIC_API_KEY in the secrets.")
            return None
        client = anthropic.Anthropic(api_key=key, timeout=TIMEOUT_SECONDS, max_retries=0)
    try:
        image = base64.standard_b64encode(shrink_photo(jpeg)).decode("ascii")
    except (OSError, ValueError):
        return None
    if not take_slot(player_id):
        return DrinkSuggestion(None, None, LIMIT_REACHED)
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            # If a safety check declines the request, the API retries it on another model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": ANSWER_SCHEMA}},
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image}},
                {"type": "text", "text": prompt_for(rules)},
            ]}],
        )
    except anthropic.APIStatusError as error:
        # The player only sees the normal form. The reason goes to the server log
        # (Streamlit Cloud: Manage app -> Logs); it never contains the key.
        log.warning("Drink recognition failed: HTTP %s %s: %s", error.status_code, type(error).__name__,
                    str(error.message)[:300])
        return None
    except (anthropic.AnthropicError, OSError, ValueError) as error:
        log.warning("Drink recognition failed: %s", type(error).__name__)
        return None
    if response.stop_reason != "end_turn":
        log.warning("Drink recognition gave no answer: stop_reason=%s", response.stop_reason)
        return None
    text = next((block.text for block in response.content if block.type == "text"), None)
    try:
        answer = json.loads(text)
    except (TypeError, ValueError):
        log.warning("Drink recognition answer was not JSON.")
        return None
    suggestion = suggestion_from_answer(answer)
    if suggestion is None:
        log.warning("Drink recognition answer did not match the expected fields.")
    else:
        # Only Claude's classification: no photo, no player, no key.
        log.info("Drink recognition answer: drink=%s (%s) size=%s (%s) several=%s visible=%s",
                 answer["drink"], answer["drink_confidence"], answer["size"], answer["size_confidence"],
                 answer["several_drinks"], answer["drink_visible"])
    return suggestion
