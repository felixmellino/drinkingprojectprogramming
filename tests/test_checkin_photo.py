from io import BytesIO
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import ExifTags, Image, TiffImagePlugin

import data.db as db
from core.checkin_photo import InvalidCheckinPhoto, prepare_checkin_photo
from core.models import DrinkEntry


def test_camera_photo_preserves_orientation_and_removes_metadata():
    rational = TiffImagePlugin.IFDRational
    exif = Image.Exif()
    exif[ExifTags.Base.Orientation] = 6
    exif[ExifTags.Base.ImageDescription] = "private camera metadata"
    exif[ExifTags.IFD.GPSInfo] = {
        1: "N", 2: (rational(38), rational(42), rational(18)),
        3: "W", 4: (rational(9), rational(8), rational(42)),
    }
    original = BytesIO()
    Image.new("RGB", (12, 6)).save(original, "JPEG", exif=exif, comment=b"private JPEG comment")

    gps, cleaned = prepare_checkin_photo(original.getvalue())

    assert gps == pytest.approx((38.705, -9.145))
    with Image.open(BytesIO(cleaned)) as saved:
        assert saved.size == (6, 12)
        assert not saved.getexif()
        assert "comment" not in saved.info


def test_unreadable_camera_photo_is_rejected():
    with pytest.raises(InvalidCheckinPhoto):
        prepare_checkin_photo(b"not a camera image")


def test_photo_download_rejects_outsider_before_requesting_image(monkeypatch):
    monkeypatch.setattr(db, "list_memberships_for_player", lambda _: [SimpleNamespace(lobby_id="other-lobby")])
    client = Mock()
    get_client = Mock(return_value=client)
    monkeypatch.setattr(db, "get_client", get_client)

    with pytest.raises(PermissionError):
        db.download_checkin_photo("reader", "photo-lobby", "entry")

    get_client.assert_not_called()


def test_photo_download_rejects_public_bucket(monkeypatch):
    monkeypatch.setattr(db, "list_memberships_for_player", lambda _: [SimpleNamespace(lobby_id="photo-lobby")])
    client = Mock()
    query = client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value.data = [{"photo_ref": "photo-lobby/entry.jpg"}]
    client.storage.get_bucket.return_value.public = True
    monkeypatch.setattr(db, "get_client", lambda: client)

    with pytest.raises(RuntimeError, match="private storage bucket"):
        db.download_checkin_photo("reader", "photo-lobby", "entry")

    client.storage.from_.assert_not_called()


def test_save_retry_recovers_committed_entry_without_uploading_again(monkeypatch):
    timestamp = datetime(2026, 11, 19, 20, tzinfo=timezone.utc)
    entry = DrinkEntry(
        id="capture", membership_id="member", season_id="season", drink_type="beer",
        amount=1, photo_ref="lobby/capture.jpg", device_gps=None, photo_gps=None,
        territory_id="shortys", location_check_result="matched", points_awarded=5,
        submitted_at=timestamp, photo_captured_at=timestamp,
    )
    monkeypatch.setattr(db, "list_memberships_for_player", lambda _: [SimpleNamespace(id="member", lobby_id="lobby")])
    monkeypatch.setattr(db, "list_seasons_for_lobby", lambda _: [SimpleNamespace(id="season")])
    client = Mock()
    client.storage.get_bucket.return_value.public = False
    table = client.table.return_value
    query = table.select.return_value
    query.eq.return_value = query
    row = db._drink_entry_row(entry)
    query.execute.side_effect = [SimpleNamespace(data=[]), SimpleNamespace(data=[row])]
    table.upsert.return_value.execute.side_effect = RuntimeError("Response lost after saving")
    monkeypatch.setattr(db, "get_client", lambda: client)

    with pytest.raises(RuntimeError, match="Response lost"):
        db.save_drink_entry_photo("player", "lobby", entry, b"clean photo")
    recovered = db.save_drink_entry_photo("player", "lobby", replace(entry, points_awarded=15), b"clean photo")

    assert recovered.points_awarded == 5
    assert recovered.photo_captured_at == timestamp
    table.upsert.assert_called_once()
    client.storage.from_.return_value.upload.assert_called_once()


def test_failed_upload_does_not_record_points(monkeypatch):
    from tests.test_checkins import IN_WINDOW_TS, INSIDE, TERRITORY
    from core.checkins import create_drink_entry
    from storage3.utils import StorageException

    entry = create_drink_entry(
        "member", "season", "beer", 1, "photo", INSIDE, None, IN_WINDOW_TS, [TERRITORY], []
    )
    monkeypatch.setattr(db, "list_memberships_for_player", lambda _: [SimpleNamespace(id="member", lobby_id="lobby")])
    monkeypatch.setattr(db, "list_seasons_for_lobby", lambda _: [SimpleNamespace(id="season")])
    client = Mock()
    client.storage.get_bucket.return_value.public = False
    client.storage.from_.return_value.upload.side_effect = StorageException("Upload failed")
    table = client.table.return_value
    query = table.select.return_value
    query.eq.return_value = query
    query.execute.return_value.data = []
    monkeypatch.setattr(db, "get_client", lambda: client)

    with pytest.raises(StorageException):
        db.save_drink_entry_photo("player", "lobby", entry, b"clean photo")

    table.upsert.assert_not_called()
