"""Shared border geometry for territory boosts and map markers."""

import math

LNG_M = 86_900
LAT_M = 110_574
BORDER_TOLERANCE_M = 0.5  # Same hand-drawn border tolerance as territory data QA.


def projected_ring(boundary):
    return [(p[0] * LNG_M, p[1] * LAT_M) for p in boundary["coordinates"][0]]


def adjacent(first, second):
    """Shared border of >0.5 m; corner-only contact and street gaps don't group.

    Projecting segment endpoints also handles a shared edge split into
    different numbers of vertices in the two hand-drawn polygons.
    """
    first_ring, second_ring = projected_ring(first), projected_ring(second)
    for first_axis, second_axis in zip(zip(*first_ring), zip(*second_ring)):
        if (max(first_axis) + BORDER_TOLERANCE_M < min(second_axis)
                or max(second_axis) + BORDER_TOLERANCE_M < min(first_axis)):
            return False
    for a, b in zip(first_ring, first_ring[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length <= BORDER_TOLERANCE_M:
            continue
        for c, d in zip(second_ring, second_ring[1:]):
            distances = [abs(dx * (p[1] - a[1]) - dy * (p[0] - a[0])) / length for p in (c, d)]
            if max(distances) > BORDER_TOLERANCE_M:
                continue
            positions = [((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length for p in (c, d)]
            overlap = min(length, max(positions)) - max(0, min(positions))
            if overlap > BORDER_TOLERANCE_M:
                return True
    return False


def boost_candidates(territories, origin):
    """Return current territories reachable through at most two shared borders."""
    boundaries = {territory.id: territory.boundary for territory in territories}
    if origin not in boundaries:
        return []
    reached = {origin}
    frontier = reached
    for _ in range(2):
        frontier = {
            territory_id for territory_id, boundary in boundaries.items()
            if territory_id not in reached
            and any(adjacent(boundaries[current], boundary) for current in frontier)
        }
        reached = reached | frontier
    return sorted(reached)
