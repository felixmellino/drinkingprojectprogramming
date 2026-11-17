"""Plain data holders for the domain. No Streamlit or database imports here."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Player:
    id: str
    display_name: str  # public username
    first_name: str  # private
    last_name: str  # private
    pin_hash: str  # credential hash; column retained to preserve existing accounts
    email: str | None = None  # None only for legacy records


@dataclass
class Lobby:
    id: str
    name: str
    invite_code: str


@dataclass
class LobbyMembership:
    id: str
    player_id: str
    lobby_id: str
    joined_at: datetime


@dataclass
class Season:
    id: str
    lobby_id: str
    starts_at: datetime
    ends_at: datetime
    length_choice: str  # "1_week" | "1_month" | "3_months"


@dataclass
class Territory:
    id: str
    name: str
    boundary: dict  # GeoJSON Polygon: {"type": "Polygon", "coordinates": [[[lng, lat], ...]]}


@dataclass
class DrinkEntry:
    id: str
    membership_id: str
    season_id: str
    drink_type: str  # "beer" | "wine" | "shot" | "longdrink"
    amount: float | None  # required for beer/wine, None for shot/longdrink
    photo_ref: str
    device_gps: tuple[float, float] | None  # (lat, lng) at submission
    photo_gps: tuple[float, float] | None  # (lat, lng) from photo EXIF, may be missing
    territory_id: str | None
    location_check_result: str  # "matched" | "uncertain" | "outside" | "unavailable"
    points_awarded: int
    submitted_at: datetime


@dataclass
class Arena:
    id: str
    name: str
    map_point: dict  # GeoJSON Point


@dataclass
class MinigameAttempt:
    id: str
    membership_id: str
    season_id: str
    arena_id: str
    game_type: str
    game_window_id: str
    started_at: datetime
    status: str  # "started" | "completed" | "interrupted"
    result: str | None
