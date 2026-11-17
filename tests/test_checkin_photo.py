from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import ExifTags, Image, TiffImagePlugin

import data.db as db
from core.checkin_photo import InvalidCheckinPhoto, prepare_checkin_photo


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
