from core.location import evaluate_location
from core.models import Territory

TERRITORY = Territory(
    id="territory-a",
    name="Bairro Alto",
    boundary={
        "type": "Polygon",
        "coordinates": [
            [[-9.15, 38.70], [-9.14, 38.70], [-9.14, 38.71], [-9.15, 38.71], [-9.15, 38.70]]
        ],
    },
)
INSIDE = (38.705, -9.145)  # lat, lng -- inside TERRITORY
OUTSIDE = (38.80, -9.00)  # far away, outside every territory
NEARBY_WITHIN_TOLERANCE = (38.7055, -9.145)  # ~55m from INSIDE
FAR_BEYOND_TOLERANCE = (38.715, -9.145)  # ~1.1km from INSIDE


def test_matched_when_device_inside_and_no_photo_gps():
    result, territory_id = evaluate_location(INSIDE, None, [TERRITORY])
    assert result == "matched"
    assert territory_id == TERRITORY.id


def test_matched_when_photo_gps_agrees_within_tolerance():
    result, territory_id = evaluate_location(INSIDE, NEARBY_WITHIN_TOLERANCE, [TERRITORY])
    assert result == "matched"
    assert territory_id == TERRITORY.id


def test_uncertain_when_photo_gps_disagrees_beyond_tolerance():
    result, territory_id = evaluate_location(INSIDE, FAR_BEYOND_TOLERANCE, [TERRITORY])
    assert result == "uncertain"
    assert territory_id == TERRITORY.id


def test_outside_every_territory():
    result, territory_id = evaluate_location(OUTSIDE, None, [TERRITORY])
    assert result == "outside"
    assert territory_id is None


def test_unavailable_when_no_device_gps():
    result, territory_id = evaluate_location(None, INSIDE, [TERRITORY])
    assert result == "unavailable"
    assert territory_id is None
