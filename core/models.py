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
    game_mode: str = "individual"
    team_count: int | None = None
    team_capacity: int | None = None
    team_assignment: str | None = None


@dataclass
class LobbyMembership:
    id: str
    player_id: str
    lobby_id: str
    joined_at: datetime
    team_id: str | None = None


@dataclass
class Team:
    id: str
    lobby_id: str
    number: int
    name: str
    photo_base64: str | None = None


@dataclass
class Season:
    id: str
    lobby_id: str
    starts_at: datetime
    ends_at: datetime
    length_choice: str  # "1_week" | "1_month" | "3_months"
    timezone_name: str = "Europe/Lisbon"
    scoring_version: str = "legacy"
    scoring_rules: dict | None = None


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
    points_awarded: int  # drinker's base award; additional owner income is separate
    submitted_at: datetime
    photo_captured_at: datetime | None = None
    size: str | None = None
    rule_version: str = "legacy"
    event_order: int | None = None
    owner_membership_id: str | None = None
    owner_bonus_quarters: int = 0
    corrected_at: datetime | None = None
    revision: int = 0
    team_id: str | None = None
    owner_team_id: str | None = None
    duel_id: str | None = None
    duel_transfer_to: str | None = None  # saved winner's competitor (team or member)
    duel_transfer_order: int | None = None  # result event, after both base entries


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
