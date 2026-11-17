"""Simple username + PIN identity. Not a full account system -- just enough
access control that one player can't act as another without their PIN."""

from __future__ import annotations

import hashlib
import hmac
import os

from core.models import Player

_PBKDF2_ITERATIONS = 200_000
_SALT_BYTES = 16


def hash_pin(pin: str) -> str:
    """Return a salted hash of `pin`, formatted as 'salt_hex:hash_hex'.
    The plaintext PIN is never stored."""
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}:{digest.hex()}"


def verify_pin(pin: str, pin_hash: str) -> bool:
    """Check `pin` against a hash produced by hash_pin()."""
    salt_hex, digest_hex = pin_hash.split(":")
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(digest_hex)
    actual = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, _PBKDF2_ITERATIONS)
    return hmac.compare_digest(actual, expected)


def authenticate(display_name: str, pin: str, players: list[Player]) -> Player | None:
    """Return the Player matching `display_name` if `pin` is correct, else None."""
    for player in players:
        if player.display_name == display_name:
            return player if verify_pin(pin, player.pin_hash) else None
    return None
