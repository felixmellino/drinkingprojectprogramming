"""The one file that talks to Supabase. Thin CRUD wrappers only -- no game
rules here. Pages call these functions and pass plain values; everything
else (validation, scoring, standings) lives in core/.

Server-only credentials come from .streamlit/secrets.toml (SUPABASE_URL /
SUPABASE_KEY), which is gitignored -- see .streamlit/secrets.toml.example.
"""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from core.auth import new_token, token_hash
from core.checkin_photo import photo_expires_at
from core.constants import UNLINKED_PHOTO_GRACE_HOURS

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

    endpoint = urlsplit(url)
    local_http = endpoint.scheme == "http" and endpoint.hostname in ("localhost", "127.0.0.1", "::1")
    if not endpoint.hostname or (endpoint.scheme != "https" and not local_http):
        raise RuntimeError("Supabase requires HTTPS or an HTTP endpoint on localhost.")

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
            email=r.get("email"),
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
            "email": player.email,
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


def upsert_territories(territories: list[Territory]) -> None:
    """Copy territories into the table, inserting new ids and updating the
    name and outline of existing ones. Territories removed from the file are
    left in the table so older drink entries still point at a valid row."""
    if not territories:
        return
    get_client().table("territories").upsert(
        [{"id": t.id, "name": t.name, "boundary": t.boundary} for t in territories]
    ).execute()


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
    row = {
        "id": entry.id,
        "membership_id": entry.membership_id,
        "season_id": entry.season_id,
        "drink_type": entry.drink_type,
        "amount": entry.amount,
        "photo_ref": entry.photo_ref,
        # Verification is finished before persistence. Never keep exact GPS.
        "device_gps_lat": None,
        "device_gps_lng": None,
        "photo_gps_lat": None,
        "photo_gps_lng": None,
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
            "seasons!inner(lobby_id,ends_at),lobby_memberships!inner(lobby_id,player_id,players(display_name))"
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
            "is_owner": row["lobby_memberships"]["player_id"] == player_id,
            "has_photo": row["photo_ref"] == _checkin_photo_path(lobby_id, row["id"]),
        }
        for row in rows
        if datetime.now(timezone.utc) < photo_expires_at(datetime.fromisoformat(row["seasons"]["ends_at"]))
    ]


def download_checkin_photo(player_id: str, lobby_id: str, entry_id: str) -> bytes | None:
    rows = _lobby_photo_query(player_id, lobby_id).eq("id", entry_id).execute().data
    photo_path = _checkin_photo_path(lobby_id, entry_id)
    if not rows or rows[0]["photo_ref"] != photo_path:
        return None
    if datetime.now(timezone.utc) >= photo_expires_at(datetime.fromisoformat(rows[0]["seasons"]["ends_at"])):
        return None
    return _private_photo_bucket().download(photo_path)


def delete_checkin_photo(player_id: str, lobby_id: str, entry_id: str) -> None:
    """Remove the owner's image while preserving the entry and its score."""
    rows = _lobby_photo_query(player_id, lobby_id).eq("id", entry_id).execute().data
    if not rows or rows[0]["lobby_memberships"]["player_id"] != player_id:
        raise PermissionError("Only the photo's owner can delete it.")
    path = _checkin_photo_path(lobby_id, entry_id)
    if rows[0]["photo_ref"] != path:
        return
    _private_photo_bucket().remove([path])
    # Removing an already absent object is safe when a previous reply was lost.
    _mark_photo_removed(entry_id, path, "deleted")


def _mark_photo_removed(entry_id: str, path: str, reason: str) -> None:
    (get_client().table("drink_entries").update({"photo_ref": reason})
     .eq("id", entry_id).eq("photo_ref", path).execute())


def _list_photo_folder(bucket, path: str) -> list[dict]:
    """Read every page before deleting objects so offsets remain stable."""
    objects = []
    while True:
        batch = bucket.list(path, {"limit": 100, "offset": len(objects), "sortBy": {"column": "name", "order": "asc"}})
        objects.extend(batch)
        if len(batch) < 100:
            return objects


def cleanup_checkin_photos(*, apply: bool = False) -> dict[str, int]:
    """Server maintenance: expired images and abandoned uploads, never scores.

    Dry run by default. Only inspect the lobby/entry.jpg layout generated here.
    Unlinked uploads get 24 hours for a failed check-in save to be retried.
    """
    bucket = _private_photo_bucket()
    now = datetime.now(timezone.utc)
    counts = {"expired": 0, "unlinked": 0}
    for folder in _list_photo_folder(bucket, ""):
        lobby_id = folder["name"]
        if folder.get("id") is not None or not lobby_id or "/" in lobby_id or lobby_id in (".", ".."):
            continue
        for obj in _list_photo_folder(bucket, lobby_id):
            name = obj["name"]
            if not obj.get("id") or not name.endswith(".jpg") or "/" in name:
                continue
            entry_id = name[:-4]
            path = _checkin_photo_path(lobby_id, entry_id)
            rows = (get_client().table("drink_entries").select("id,photo_ref,seasons!inner(ends_at)")
                    .eq("id", entry_id).eq("photo_ref", path).execute().data)
            if rows:
                if now < photo_expires_at(datetime.fromisoformat(rows[0]["seasons"]["ends_at"])):
                    continue
                reason = "expired"
            else:
                # Missing timestamps fail closed: do not guess an upload's age.
                modified = obj.get("updated_at") or obj.get("created_at")
                if not modified:
                    continue
                modified_at = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                if modified_at.tzinfo is None:
                    modified_at = modified_at.replace(tzinfo=timezone.utc)
                if now < modified_at + timedelta(hours=UNLINKED_PHOTO_GRACE_HOURS):
                    continue
                reason = "unlinked"
            if apply:
                bucket.remove([path])
                if rows:
                    _mark_photo_removed(entry_id, path, "expired")
            counts[reason] += 1
    return counts


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


def get_player(player_id: str) -> Player | None:
    rows = get_client().table("players").select("*").eq("id", player_id).execute().data
    return Player(**rows[0]) if rows else None


def allow_login_attempt(player_id: str) -> bool:
    return bool(get_client().rpc("allow_login_attempt", {"target_player": player_id}).execute().data)


# The browser stores only the random token; Supabase stores only its hash.
def create_remembered_session(player: Player) -> str:
    token, stored_hash = new_token()
    get_client().table("remembered_sessions").insert({
        "token_hash": stored_hash, "player_id": player.id,
        "credential_version": token_hash(player.pin_hash),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    }).execute()
    return token


def get_remembered_player(token: str) -> Player | None:
    if not 40 <= len(token) <= 100:
        return None
    rows = (get_client().table("remembered_sessions").select("*")
            .eq("token_hash", token_hash(token)).execute().data)
    if not rows:
        return None
    session = rows[0]
    player = get_player(session["player_id"])
    if (datetime.fromisoformat(session["expires_at"]) <= datetime.now(timezone.utc)
            or not player or not player.email
            or session["credential_version"] != token_hash(player.pin_hash)):
        revoke_remembered_session(token)
        return None
    return player


def revoke_remembered_session(token: str) -> None:
    get_client().table("remembered_sessions").delete().eq("token_hash", token_hash(token)).execute()


# -- private friendships (call only after require_login) -----------------

def list_public_usernames() -> list[dict]:
    """Fetch no names, emails or credential hashes for friend search."""
    # Page through the directory so search includes users beyond Supabase's
    # default 1,000-row response limit.
    users = []
    offset = 0
    while True:
        rows = get_client().table("players").select("id,display_name").order("id").range(offset, offset + 999).execute().data
        users.extend(rows)
        if len(rows) < 1000:
            return users
        offset += 1000


def list_friendships(player_id: str) -> list[dict]:
    """Only this authenticated player's relationships; never another list."""
    rows = []
    offset = 0
    while True:
        page = (get_client().table("friendships").select("*")
                .or_(f"sender_id.eq.{player_id},recipient_id.eq.{player_id}")
                .order("pair_low").order("pair_high").range(offset, offset + 999).execute().data)
        rows.extend(page)
        if len(page) < 1000:
            return rows
        offset += 1000


def change_friendship(player_id: str, other_id: str, action: str) -> None:
    from core.friends import transition

    low, high = sorted((player_id, other_id))
    rows = (get_client().table("friendships").select("*")
            .eq("pair_low", low).eq("pair_high", high).execute().data)
    current = rows[0] if rows else None
    next_row = transition(player_id, other_id, action, current, datetime.now(timezone.utc))
    get_client().rpc("save_friendship", {
        "sender": next_row["sender_id"], "recipient": next_row["recipient_id"],
        "next_status": next_row["status"],
        "expected_version": current["version"] if current else None,
    }).execute()
