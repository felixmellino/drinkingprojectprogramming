"""Read the location evidence and prepare a camera photo for private storage."""

from __future__ import annotations

from io import BytesIO
from math import isfinite
from warnings import catch_warnings, simplefilter

from PIL import ExifTags, Image, ImageOps


class InvalidCheckinPhoto(ValueError):
    """The camera image could not be decoded safely."""


def _photo_gps(image: Image.Image) -> tuple[float, float] | None:
    try:
        gps = image.getexif().get_ifd(ExifTags.IFD.GPSInfo)
        if gps[1] not in ("N", "S") or gps[3] not in ("E", "W"):
            return None
        lat = _decimal_degrees(gps[2], gps[1])
        lng = _decimal_degrees(gps[4], gps[3])
        if isfinite(lat) and isfinite(lng) and abs(lat) <= 90 and abs(lng) <= 180:
            return lat, lng
    except (KeyError, OSError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        # Phone cameras can omit GPS or supply incomplete metadata.
        pass
    return None


def _decimal_degrees(value, direction: str) -> float:
    degrees, minutes, seconds = value
    decimal = float(degrees + minutes / 60 + seconds / 3600)
    return -decimal if direction in ("S", "W") else decimal


def prepare_checkin_photo(camera_bytes: bytes) -> tuple[tuple[float, float] | None, bytes]:
    """Return optional GPS evidence and a JPEG containing only image pixels."""
    output = BytesIO()
    try:
        with catch_warnings():
            simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(camera_bytes), formats=("JPEG",)) as original:
                gps = _photo_gps(original)
                with ImageOps.exif_transpose(original).convert("RGB") as oriented:
                    with Image.frombytes("RGB", oriented.size, oriented.tobytes()) as clean:
                        clean.save(output, format="JPEG", quality=90)
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise InvalidCheckinPhoto("Take a new photo. This image could not be read.") from error
    return gps, output.getvalue()
