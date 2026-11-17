"""Matching the phone's GPS reading to a territory (R-L01 to R-L03).

location_check_result meanings:
- "unavailable": no phone GPS reading at all.
- "uncertain": the phone says its reading may be off by more than
  MAX_GPS_ACCURACY_M (R-L02), or the point lies in more than one territory
  (overlapping outlines; R-T02 and its test prevent this).
- "matched": the point lies inside exactly one territory. Being close to a
  border does not matter (R-L03).
- "outside": the point lies inside no territory.

Photo GPS is not used (R-L01).
"""

from __future__ import annotations

from core.constants import MAX_GPS_ACCURACY_M
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


def evaluate_location(
    device_gps: GPS | None,
    accuracy_m: float | None,
    territories: list[Territory],
) -> tuple[str, str | None]:
    """Return (location_check_result, territory_id).

    `accuracy_m` is how many metres the phone says its reading may be off.
    None means no accuracy was reported: today that is the manual
    latitude/longitude entry on the Check-in page, which is accepted until
    real phone GPS replaces it. A territory id is only returned for
    "matched", so an uncertain reading never silently gets a territory."""
    if device_gps is None:
        return "unavailable", None
    if accuracy_m is not None and accuracy_m > MAX_GPS_ACCURACY_M:
        return "uncertain", None

    matches = find_matching_territories(device_gps[0], device_gps[1], territories)
    if len(matches) > 1:
        return "uncertain", None
    if len(matches) == 1:
        return "matched", matches[0].id
    return "outside", None
