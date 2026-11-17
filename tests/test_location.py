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
NEAR_EDGE = (38.705, -9.1401)  # inside TERRITORY, about 9 m from its east border
OUTSIDE = (38.80, -9.00)  # far away, outside every territory


def test_matched_when_inside_and_accuracy_is_good():
    result, territory_id = evaluate_location(INSIDE, 10.0, [TERRITORY])
    assert result == "matched"
    assert territory_id == TERRITORY.id


def test_matched_when_no_accuracy_is_reported():
    """Manual coordinates report no accuracy; accepted until real GPS."""
    result, territory_id = evaluate_location(INSIDE, None, [TERRITORY])
    assert result == "matched"
    assert territory_id == TERRITORY.id


def test_exactly_50_m_accuracy_is_accepted():
    """Boundary case of R-L02."""
    result, _ = evaluate_location(INSIDE, 50.0, [TERRITORY])
    assert result == "matched"


def test_worse_than_50_m_accuracy_is_uncertain_without_a_territory():
    """Rejected case of R-L02: no territory is assigned silently."""
    result, territory_id = evaluate_location(INSIDE, 50.1, [TERRITORY])
    assert result == "uncertain"
    assert territory_id is None


def test_point_near_a_border_belongs_to_the_territory_it_is_in():
    """R-L03: the accuracy circle (40 m) crosses the border, the point decides."""
    result, territory_id = evaluate_location(NEAR_EDGE, 40.0, [TERRITORY])
    assert result == "matched"
    assert territory_id == TERRITORY.id


def test_outside_every_territory():
    result, territory_id = evaluate_location(OUTSIDE, 10.0, [TERRITORY])
    assert result == "outside"
    assert territory_id is None


def test_unavailable_when_no_phone_gps():
    result, territory_id = evaluate_location(None, 10.0, [TERRITORY])
    assert result == "unavailable"
    assert territory_id is None


def test_overlapping_territories_are_uncertain():
    """Defensive: R-T02 forbids overlap, but if it happens, assign nothing."""
    twin = Territory(id="territory-b", name="Twin", boundary=TERRITORY.boundary)
    result, territory_id = evaluate_location(INSIDE, 10.0, [TERRITORY, twin])
    assert result == "uncertain"
    assert territory_id is None
