"""Matching a drink's location evidence to a territory.

location_check_result meanings:
- "unavailable": no device GPS reading at all.
- "matched": device GPS is inside exactly one territory, and (if a photo
  GPS reading exists) it agrees with the device GPS within tolerance.
- "uncertain": device GPS and photo GPS disagree beyond tolerance, or the
  device GPS matches more than one territory (overlapping polygons; should
  not normally happen with well-drawn territories).
- "outside": device GPS doesn't fall inside any territory.
"""

from __future__ import annotations

import math

from core.constants import GPS_MISMATCH_TOLERANCE_M
from core.models import Territory

GPS = tuple[float, float]  # (lat, lng)


def point_in_polygon(lat: float, lng: float, polygon_coords: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon test over a GeoJSON exterior ring
    (a list of [lng, lat] pairs). Does not support holes."""
    inside = False
    n = len(polygon_coords)
    j = n - 1
    for i in range(n):
        xi, yi = polygon_coords[i][0], polygon_coords[i][1]
        xj, yj = polygon_coords[j][0], polygon_coords[j][1]
        if ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside


def find_matching_territories(lat: float, lng: float, territories: list[Territory]) -> list[Territory]:
    matches = []
    for territory in territories:
        ring = territory.boundary["coordinates"][0]
        if point_in_polygon(lat, lng, ring):
            matches.append(territory)
    return matches


def haversine_distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    earth_radius_m = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return earth_radius_m * 2 * math.asin(math.sqrt(a))


def gps_mismatch(device_gps: GPS, photo_gps: GPS | None) -> bool:
    if photo_gps is None:
        return False
    distance = haversine_distance_m(device_gps[0], device_gps[1], photo_gps[0], photo_gps[1])
    return distance > GPS_MISMATCH_TOLERANCE_M


def evaluate_location(
    device_gps: GPS | None,
    photo_gps: GPS | None,
    territories: list[Territory],
) -> tuple[str, str | None]:
    """Return (location_check_result, territory_id)."""
    if device_gps is None:
        return "unavailable", None

    matches = find_matching_territories(device_gps[0], device_gps[1], territories)
    mismatch = gps_mismatch(device_gps, photo_gps)

    if mismatch or len(matches) > 1:
        return "uncertain", matches[0].id if matches else None
    if len(matches) == 1:
        return "matched", matches[0].id
    return "outside", None
