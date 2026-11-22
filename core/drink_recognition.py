"""Turn Claude's reading of a check-in photo into a suggestion for the form.

The suggestion only preselects the drink and size on the Check in page. The
player confirms or changes it, and the points still come from the scoring
rules (R-C01 in docs/ontology/RULES.md). Nothing here talks to the network;
drink_recognition.py in the project root sends the photo.
"""
from dataclasses import dataclass

from core.scoring_v1 import DRINK_LABELS, SIZE_LABELS, VOLUMES

DRINKS = tuple(DRINK_LABELS)             # beer, wine, shot, mixed
SIZES = tuple(SIZE_LABELS)               # small, medium, large
CONFIDENCE = ("high", "medium", "low")

# The answer Claude must give. Structured outputs make the API return exactly
# this shape; suggestion_from_answer still checks every value. There is no
# "unknown": Claude always names its best guess and says how sure it is.
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "drink_visible": {"type": "boolean"},
        "several_drinks": {"type": "boolean"},
        "drink": {"type": "string", "enum": list(DRINKS)},
        "drink_confidence": {"type": "string", "enum": list(CONFIDENCE)},
        "size": {"type": "string", "enum": [*SIZES, "none"]},
        "size_confidence": {"type": "string", "enum": list(CONFIDENCE)},
    },
    "required": ["drink_visible", "several_drinks", "drink", "drink_confidence", "size", "size_confidence"],
    "additionalProperties": False,
}

NO_DRINK = "No drink found in the photo. Choose it yourself."
LIMIT_REACHED = "Drink suggestions are paused for a while. Choose it yourself."

# Each recognition is a paid API call, so one player gets at most
# LIMIT_PER_HOUR of them in any rolling hour (R-C01).
LIMIT_PER_HOUR = 10
LIMIT_WINDOW_SECONDS = 3600


def within_limit(recent: list[float], now: float) -> tuple[bool, list[float]]:
    """Keep the call times still inside the window; allowed while fewer than the limit remain.

    A call exactly LIMIT_WINDOW_SECONDS old no longer counts.
    """
    kept = [moment for moment in recent if now - moment < LIMIT_WINDOW_SECONDS]
    return len(kept) < LIMIT_PER_HOUR, kept


@dataclass(frozen=True)
class DrinkSuggestion:
    """What to preselect (None = keep the normal default) and what to tell the player."""
    drink: str | None
    size: str | None
    message: str


def prompt_for(rules: dict | None = None) -> str:
    """The instruction sent with the photo, using the season's own volumes."""
    volumes = (rules or {}).get("volumes", VOLUMES)

    def sizes(drink):
        return ", ".join(f"{size} {ml} ml" for size, ml in volumes.get(drink, {}).items())

    return (
        "This photo was taken by a player of a bar game to log the drink they are having.\n"
        "Classify the drink in the photo.\n"
        "- drink: beer, wine, mixed (cocktail, long drink, spirit with a mixer) or shot.\n"
        f"- size for beer: {sizes('beer')}.\n"
        f"- size for wine: {sizes('wine')}.\n"
        "- size for mixed: small (short glass), medium (normal long drink), large (big glass or pitcher-sized).\n"
        "- size for shot: none. Use none only for a shot.\n"
        "Judge the size from the glass shape and from hands or objects nearby.\n"
        "Always give your most likely drink and size, even when you are unsure, "
        "and say how sure you are in the confidence fields.\n"
        "If several drinks are visible, describe the one in the foreground and set several_drinks to true.\n"
        "If no drink is visible at all, set drink_visible to false."
    )


def suggestion_from_answer(answer) -> DrinkSuggestion | None:
    """Check Claude's answer and decide what the form preselects.

    Returns None when the answer is malformed, so the page simply shows the
    normal form. Otherwise Claude's most likely drink and size are always
    preselected; the message says how sure it was. Only "no drink visible"
    preselects nothing.
    """
    if not isinstance(answer, dict) or set(answer) != set(ANSWER_SCHEMA["required"]):
        return None
    visible, several = answer["drink_visible"], answer["several_drinks"]
    drink, drink_sure = answer["drink"], answer["drink_confidence"]
    size, size_sure = answer["size"], answer["size_confidence"]
    if not isinstance(visible, bool) or not isinstance(several, bool):
        return None
    if drink not in DRINKS or size not in (*SIZES, "none"):
        return None
    if drink_sure not in CONFIDENCE or size_sure not in CONFIDENCE:
        return None

    if not visible:
        return DrinkSuggestion(None, None, NO_DRINK)
    if drink == "shot" or size == "none":
        size = None
    name = DRINK_LABELS[drink].lower()
    if drink == "shot":
        label = "a shot"
    elif size:
        label = f"a {SIZE_LABELS[size].lower()} {name}"
    else:
        label = name
    unsure = drink_sure == "low" or (size is not None and size_sure == "low")
    if several:
        message = f"Several drinks in the photo. Best guess for the one in front: {label}. Check it before you submit."
    elif unsure:
        message = f"Best guess: {label}. Check it before you submit."
    elif drink != "shot" and size is None:
        message = f"Looks like {label}. Check the size."
    else:
        message = f"Looks like {label}. Change it if that's wrong."
    return DrinkSuggestion(drink, size, message)
