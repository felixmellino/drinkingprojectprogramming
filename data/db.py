"""The one file that talks to Supabase. Thin CRUD wrappers only -- no game
rules here. Pages call these functions and pass plain values; everything
else (validation, scoring, standings) lives in core/.

The connection string comes from .streamlit/secrets.toml (SUPABASE_URL /
SUPABASE_KEY), which is gitignored -- see .streamlit/secrets.toml.example.
"""

from __future__ import annotations

import os
from datetime import datetime

from supabase import Client, create_client

from core.models import Arena, DrinkEntry, Lobby, LobbyMembership, MinigameAttempt, Player, Season, Territory

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is not None:
        return _client

    url = None
    key = None
    try:
        import streamlit as st

        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
    except Exception:
        pass

    url = url or os.environ.get("SUPABASE_URL")
    key = key or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Supabase credentials missing. Set SUPABASE_URL and SUPABASE_KEY "
            "in .streamlit/secrets.toml (see secrets.toml.example)."
        )

    _client = create_client(url, key)
    return _client


# -- players -----------------------------------------------------------

def list_players() -> list[Player]:
    rows = get_client().table("players").select("*").execute().data
    return [
        Player(
            id=r["id"],
            display_name=r["display_name"],
            first_name=r["first_name"],
            last_name=r["last_name"],
            pin_hash=r["pin_hash"],
        )
        for r in rows
    ]


def insert_player(player: Player) -> None:
    get_client().table("players").insert(
        {
            "id": player.id,
            "display_name": player.display_name,
            "first_name": player.first_name,
            "last_name": player.last_name,
            "pin_hash": player.pin_hash,
        }
    ).execute()


# -- lobbies & memberships ------------------------------------------------

def list_lobbies() -> list[Lobby]:
    rows = get_client().table("lobbies").select("*").execute().data
    return [Lobby(id=r["id"], name=r["name"], invite_code=r["invite_code"]) for r in rows]


def insert_lobby(lobby: Lobby) -> None:
    get_client().table("lobbies").insert(
        {"id": lobby.id, "name": lobby.name, "invite_code": lobby.invite_code}
    ).execute()


def list_memberships_for_player(player_id: str) -> list[LobbyMembership]:
    rows = get_client().table("lobby_memberships").select("*").eq("player_id", player_id).execute().data
    return [
        LobbyMembership(
            id=r["id"],
            player_id=r["player_id"],
            lobby_id=r["lobby_id"],
            joined_at=datetime.fromisoformat(r["joined_at"]),
        )
        for r in rows
    ]


def list_memberships_for_lobby(lobby_id: str) -> list[LobbyMembership]:
    rows = get_client().table("lobby_memberships").select("*").eq("lobby_id", lobby_id).execute().data
    return [
        LobbyMembership(
            id=r["id"],
            player_id=r["player_id"],
            lobby_id=r["lobby_id"],
            joined_at=datetime.fromisoformat(r["joined_at"]),
        )
        for r in rows
    ]


def insert_membership(membership: LobbyMembership) -> None:
    get_client().table("lobby_memberships").insert(
        {
            "id": membership.id,
            "player_id": membership.player_id,
            "lobby_id": membership.lobby_id,
            "joined_at": membership.joined_at.isoformat(),
        }
    ).execute()


# -- seasons ----------------------------------------------------------

def list_seasons_for_lobby(lobby_id: str) -> list[Season]:
    rows = get_client().table("seasons").select("*").eq("lobby_id", lobby_id).execute().data
    return [
        Season(
            id=r["id"],
            lobby_id=r["lobby_id"],
            starts_at=datetime.fromisoformat(r["starts_at"]),
            ends_at=datetime.fromisoformat(r["ends_at"]),
            length_choice=r["length_choice"],
        )
        for r in rows
    ]


def insert_season(season: Season) -> None:
    get_client().table("seasons").insert(
        {
            "id": season.id,
            "lobby_id": season.lobby_id,
            "starts_at": season.starts_at.isoformat(),
            "ends_at": season.ends_at.isoformat(),
            "length_choice": season.length_choice,
        }
    ).execute()


# -- territories & arenas -------------------------------------------------

def list_territories() -> list[Territory]:
    rows = get_client().table("territories").select("*").execute().data
    return [Territory(id=r["id"], name=r["name"], boundary=r["boundary"]) for r in rows]


def list_arenas() -> list[Arena]:
    rows = get_client().table("arenas").select("*").execute().data
    return [Arena(id=r["id"], name=r["name"], map_point=r["map_point"]) for r in rows]


# -- drink entries -------------------------------------------------------

def list_drink_entries(season_id: str) -> list[DrinkEntry]:
    rows = get_client().table("drink_entries").select("*").eq("season_id", season_id).execute().data
    return [_row_to_drink_entry(r) for r in rows]


def list_drink_entries_for_membership(membership_id: str) -> list[DrinkEntry]:
    rows = get_client().table("drink_entries").select("*").eq("membership_id", membership_id).execute().data
    return [_row_to_drink_entry(r) for r in rows]


def _row_to_drink_entry(r: dict) -> DrinkEntry:
    device_gps = None
    if r.get("device_gps_lat") is not None and r.get("device_gps_lng") is not None:
        device_gps = (r["device_gps_lat"], r["device_gps_lng"])
    photo_gps = None
    if r.get("photo_gps_lat") is not None and r.get("photo_gps_lng") is not None:
        photo_gps = (r["photo_gps_lat"], r["photo_gps_lng"])
    return DrinkEntry(
        id=r["id"],
        membership_id=r["membership_id"],
        season_id=r["season_id"],
        drink_type=r["drink_type"],
        amount=r.get("amount"),
        photo_ref=r["photo_ref"],
        device_gps=device_gps,
        photo_gps=photo_gps,
        territory_id=r.get("territory_id"),
        location_check_result=r["location_check_result"],
        points_awarded=r["points_awarded"],
        submitted_at=datetime.fromisoformat(r["submitted_at"]),
    )


def insert_drink_entry(entry: DrinkEntry) -> None:
    device_lat, device_lng = entry.device_gps if entry.device_gps else (None, None)
    photo_lat, photo_lng = entry.photo_gps if entry.photo_gps else (None, None)
    get_client().table("drink_entries").insert(
        {
            "id": entry.id,
            "membership_id": entry.membership_id,
            "season_id": entry.season_id,
            "drink_type": entry.drink_type,
            "amount": entry.amount,
            "photo_ref": entry.photo_ref,
            "device_gps_lat": device_lat,
            "device_gps_lng": device_lng,
            "photo_gps_lat": photo_lat,
            "photo_gps_lng": photo_lng,
            "territory_id": entry.territory_id,
            "location_check_result": entry.location_check_result,
            "points_awarded": entry.points_awarded,
            "submitted_at": entry.submitted_at.isoformat(),
        }
    ).execute()


# -- minigame attempts ------------------------------------------------

def list_minigame_attempts_for_membership(membership_id: str) -> list[MinigameAttempt]:
    rows = (
        get_client()
        .table("minigame_attempts")
        .select("*")
        .eq("membership_id", membership_id)
        .execute()
        .data
    )
    return [
        MinigameAttempt(
            id=r["id"],
            membership_id=r["membership_id"],
            season_id=r["season_id"],
            arena_id=r["arena_id"],
            game_type=r["game_type"],
            game_window_id=r["game_window_id"],
            started_at=datetime.fromisoformat(r["started_at"]),
            status=r["status"],
            result=r.get("result"),
        )
        for r in rows
    ]


def insert_minigame_attempt(attempt: MinigameAttempt) -> None:
    get_client().table("minigame_attempts").insert(
        {
            "id": attempt.id,
            "membership_id": attempt.membership_id,
            "season_id": attempt.season_id,
            "arena_id": attempt.arena_id,
            "game_type": attempt.game_type,
            "game_window_id": attempt.game_window_id,
            "started_at": attempt.started_at.isoformat(),
            "status": attempt.status,
            "result": attempt.result,
        }
    ).execute()
