"""Players, lobbies, memberships, and seasons."""

from __future__ import annotations

import random
import string
import uuid
from datetime import datetime, timedelta

from core.auth import hash_password, validate_account
from core.constants import SEASON_LENGTH_DAYS
from core.models import Lobby, LobbyMembership, Player, Season

# Excludes visually ambiguous characters (0/O, 1/I).
_INVITE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_invite_code(length: int = 6) -> str:
    return "".join(random.choice(_INVITE_CODE_ALPHABET) for _ in range(length))


def create_player(display_name: str, first_name: str, last_name: str, email: str,
                  password: str, confirmation: str, players: list[Player]) -> Player:
    first_name, last_name, display_name, email = validate_account(
        first_name, last_name, display_name, email, password, confirmation, players
    )
    return Player(
        id=str(uuid.uuid4()), display_name=display_name, first_name=first_name,
        last_name=last_name, email=email, pin_hash=hash_password(password),
    )


def create_lobby(name: str) -> Lobby:
    if not name:
        raise ValueError("name is required")
    return Lobby(id=str(uuid.uuid4()), name=name, invite_code=generate_invite_code())


def join_lobby(
    player_id: str,
    invite_code: str,
    lobbies: list[Lobby],
    existing_memberships: list[LobbyMembership],
) -> LobbyMembership:
    """Join a lobby by invite code. Raises ValueError for an unknown code.
    Joining the same lobby twice returns the existing membership instead of
    creating a second one."""
    lobby = next((l for l in lobbies if l.invite_code == invite_code), None)
    if lobby is None:
        raise ValueError("invalid invite code")

    for membership in existing_memberships:
        if membership.player_id == player_id and membership.lobby_id == lobby.id:
            return membership

    return LobbyMembership(
        id=str(uuid.uuid4()),
        player_id=player_id,
        lobby_id=lobby.id,
        joined_at=datetime.now(),
    )


def create_season(lobby_id: str, length_choice: str, starts_at: datetime) -> Season:
    if length_choice not in SEASON_LENGTH_DAYS:
        raise ValueError(f"unknown season length: {length_choice}")
    ends_at = starts_at + timedelta(days=SEASON_LENGTH_DAYS[length_choice])
    return Season(
        id=str(uuid.uuid4()),
        lobby_id=lobby_id,
        starts_at=starts_at,
        ends_at=ends_at,
        length_choice=length_choice,
    )
