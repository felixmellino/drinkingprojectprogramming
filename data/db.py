"""The one file that talks to Supabase. Thin CRUD wrappers only -- no game
rules here. Pages call these functions and pass plain values; everything
else (validation, scoring, standings) lives in core/.

The connection string comes from .streamlit/secrets.toml (SUPABASE_URL /
SUPABASE_KEY), which is gitignored -- see .streamlit/secrets.toml.example.
"""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime

from supabase import Client, create_client

from core.models import Arena, DrinkEntry, Lobby, LobbyMembership, MinigameAttempt, Player, Season, Territory

_client: Client | None = None
CHECKIN_PHOTO_BUCKET = "check-in-photos"


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
        photo_captured_at=datetime.fromisoformat(r["photo_captured_at"]) if r.get("photo_captured_at") else None,
    )


def _drink_entry_row(entry: DrinkEntry) -> dict:
    device_lat, device_lng = entry.device_gps if entry.device_gps else (None, None)
    photo_lat, photo_lng = entry.photo_gps if entry.photo_gps else (None, None)
    row = {
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
    if entry.photo_captured_at is not None:
        row["photo_captured_at"] = entry.photo_captured_at.isoformat()
    return row


def insert_drink_entry(entry: DrinkEntry) -> None:
    get_client().table("drink_entries").insert(_drink_entry_row(entry)).execute()


def _checkin_photo_path(lobby_id: str, entry_id: str) -> str:
    return f"{lobby_id}/{entry_id}.jpg"


def _private_photo_bucket():
    storage = get_client().storage
    if storage.get_bucket(CHECKIN_PHOTO_BUCKET).public is not False:
        raise RuntimeError("Check-in photos require a private storage bucket.")
    return storage.from_(CHECKIN_PHOTO_BUCKET)


def save_drink_entry_photo(player_id: str, lobby_id: str, entry: DrinkEntry, photo: bytes) -> DrinkEntry:
    """Save the photo first, then record points once for this camera capture."""
    if not any(
        member.id == entry.membership_id and member.lobby_id == lobby_id
        for member in list_memberships_for_player(player_id)
    ) or not any(season.id == entry.season_id for season in list_seasons_for_lobby(lobby_id)):
        raise PermissionError("The player and season must belong to this lobby.")

    table = get_client().table("drink_entries")
    saved = table.select("*").eq("id", entry.id).eq("membership_id", entry.membership_id).execute().data
    if saved:
        return _row_to_drink_entry(saved[0])

    photo_path = _checkin_photo_path(lobby_id, entry.id)
    _private_photo_bucket().upload(photo_path, photo, {"content-type": "image/jpeg", "upsert": "true"})
    # Retrying the same capture uses the same object path and primary key.
    saved = table.upsert(
        _drink_entry_row(replace(entry, photo_ref=photo_path)),
        on_conflict="id",
        ignore_duplicates=True,
    ).execute().data
    if not saved:
        saved = table.select("*").eq("id", entry.id).eq("membership_id", entry.membership_id).execute().data
    if not saved:
        raise RuntimeError("Could not confirm the check-in was saved.")
    return _row_to_drink_entry(saved[0])


def _lobby_photo_query(player_id: str, lobby_id: str):
    if not any(member.lobby_id == lobby_id for member in list_memberships_for_player(player_id)):
        raise PermissionError("Only members of this lobby can view its check-in photos.")

    return (
        get_client().table("drink_entries")
        .select(
            "id,photo_ref,photo_captured_at,submitted_at,location_check_result,territories(name),"
            "seasons!inner(lobby_id),lobby_memberships!inner(lobby_id,players(display_name))"
        )
        .eq("seasons.lobby_id", lobby_id)
        .eq("lobby_memberships.lobby_id", lobby_id)
    )


def list_checkin_photos(player_id: str, lobby_id: str) -> list[dict]:
    rows = _lobby_photo_query(player_id, lobby_id).order("submitted_at", desc=True).execute().data
    return [
        {
            "id": row["id"],
            "username": row["lobby_memberships"]["players"]["display_name"],
            "territory": row["territories"]["name"] if row["territories"] else None,
            "location": row["location_check_result"],
            "captured_at": row.get("photo_captured_at"),
            "submitted_at": row["submitted_at"],
        }
        for row in rows
    ]


def download_checkin_photo(player_id: str, lobby_id: str, entry_id: str) -> bytes | None:
    rows = _lobby_photo_query(player_id, lobby_id).eq("id", entry_id).execute().data
    photo_path = _checkin_photo_path(lobby_id, entry_id)
    if not rows or rows[0]["photo_ref"] != photo_path:
        return None
    return _private_photo_bucket().download(photo_path)


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
