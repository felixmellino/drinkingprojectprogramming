"""Account validation and credentials, independent of the UI and database."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from collections import deque
from threading import Lock
from time import monotonic

from core.models import Player

_PBKDF2_ITERATIONS = 600_000
_LEGACY_ITERATIONS = 200_000
_UNKNOWN_LOGIN_WINDOW_SECONDS = 60
_UNKNOWN_LOGIN_LIMIT = 30
_unknown_login_attempts: deque[float] = deque()
_unknown_login_lock = Lock()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{_PBKDF2_ITERATIONS}:{salt.hex()}:{digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if len(password) > 1024:
        return False
    try:
        parts = stored_hash.split(":")
        if len(parts) == 2:  # Existing username/PIN accounts.
            iterations = _LEGACY_ITERATIONS
            salt_hex, digest_hex = parts
        else:
            iterations_text, salt_hex, digest_hex = parts
            iterations = int(iterations_text)
        if not 1 <= iterations <= _PBKDF2_ITERATIONS:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), iterations)
        return hmac.compare_digest(actual, bytes.fromhex(digest_hex))
    except (ValueError, TypeError, AttributeError):
        return False


def normalize_email(email: str) -> str:
    email = email.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", email):
        raise ValueError("Enter a valid email address.")
    return email


def validate_password(password: str, confirmation: str) -> None:
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")
    if len(password) > 1024:
        raise ValueError("Password must contain at most 1024 characters.")
    if password.isspace():
        raise ValueError("Password cannot contain only spaces. Include letters, numbers or other non-space characters.")
    if password != confirmation:
        raise ValueError("Passwords do not match. Enter the same password in both password fields.")


def validate_profile_names(first_name, last_name, username):
    """Shared name rules for registration and subsequent profile edits."""
    first_name, last_name, username = (s.strip() for s in (first_name, last_name, username))
    if not first_name or not last_name or not username:
        raise ValueError("First name, surname and username are required. Fill in all three fields.")
    if max(len(first_name), len(last_name), len(username)) > 100:
        raise ValueError("Names and username must contain at most 100 characters each.")
    return first_name, last_name, username


def validate_account(first_name, last_name, username, email, password, confirmation, players, player_id=None):
    """Return trimmed account fields; reject empty/duplicate input before writing."""
    first_name, last_name, username = validate_profile_names(first_name, last_name, username)
    email = normalize_email(email)
    validate_password(password, confirmation)
    for player in players:
        if player.id == player_id:
            continue
        if player.display_name.strip().lower() == username.lower():
            raise ValueError("That username is already taken. Enter a different username.")
        if player.email and player.email.strip().lower() == email:
            raise ValueError("That email is already registered. Log in to your existing account or use Forgot password.")
    return first_name, last_name, username, email


# A fixed dummy hash ensures unknown emails still perform password hashing.
_DUMMY_HASH = f"{_PBKDF2_ITERATIONS}:" + "00" * 16 + ":" + "00" * 32


def allow_unknown_login_attempt() -> bool:
    """Cap dummy password checks per server process, across all unknown addresses."""
    with _unknown_login_lock:
        now = monotonic()
        cutoff = now - _UNKNOWN_LOGIN_WINDOW_SECONDS
        while _unknown_login_attempts and _unknown_login_attempts[0] <= cutoff:
            _unknown_login_attempts.popleft()
        if len(_unknown_login_attempts) >= _UNKNOWN_LOGIN_LIMIT:
            return False
        _unknown_login_attempts.append(now)
        return True


def authenticate(email: str, password: str, candidate: Player | None) -> Player | None:
    if candidate is not None and (not candidate.email or candidate.email.lower() != email.strip().lower()):
        candidate = None
    valid = verify_password(password, candidate.pin_hash if candidate else _DUMMY_HASH)
    return candidate if valid else None


def new_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, token_hash(token)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.strip().encode()).hexdigest()
