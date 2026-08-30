"""2D geometry utilities for polygon processing."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import TYPE_CHECKING, Protocol, cast

from lsmesher.geometry_types import Edge, Point2D

if TYPE_CHECKING:
    from collections.abc import Sequence


class RandomSource(Protocol):
    """Uniform random source used for region sampling."""

    def uniform(self, a: float, b: float) -> float: ...


def triangle_area(p1: Point2D, p2: Point2D, p3: Point2D) -> float:
    """Double the absolute area of the triangle formed by p1, p2, p3."""
    return abs(p1.x * (p2.y - p3.y) + p2.x * (p3.y - p1.y) + p3.x * (p1.y - p2.y))


def remove_collinear(
    points: Sequence[Point2D],
    edges: Sequence[Edge],
    epsilon: float = 1e-3,
) -> tuple[list[Point2D], list[Edge]]:
    """Remove collinear points from a polygon."""
    if len(edges) < 2:
        return list(points), list(edges)
    done = False
    candidate_edges = {edge.sorted().as_tuple() for edge in edges}
    while not done:
        done = True
        adjacency: dict[int, list[int]] = {i: [] for i in range(len(points))}
        for i, j in candidate_edges:
            adjacency[i].append(j)
            adjacency[j].append(i)
        for i, j in list(candidate_edges):
            # Only collapse vertices in the interior of a simple polyline.
            # Merged material interfaces contain degree-three junctions; picking
            # an arbitrary neighbour there deletes one branch and opens the PSLG.
            ki = next((p for p in adjacency[i] if p != j), None)
            kj = next((p for p in adjacency[j] if p != i), None)
            if (
                len(adjacency[i]) == 2
                and ki is not None
                and triangle_area(points[i], points[j], points[ki]) <= epsilon
            ):
                candidate_edges.discard(tuple(sorted((ki, i))))
                candidate_edges.discard(tuple(sorted((i, j))))
                candidate_edges.add(tuple(sorted((ki, j))))
                done = False
                break
            if (
                len(adjacency[j]) == 2
                and kj is not None
                and triangle_area(points[i], points[j], points[kj]) <= epsilon
            ):
                candidate_edges.discard(tuple(sorted((i, j))))
                candidate_edges.discard(tuple(sorted((j, kj))))
                candidate_edges.add(tuple(sorted((i, kj))))
                done = False
                break

    used_indices = {i for e in candidate_edges for i in e}

    index_map = {}
    new_points: list[Point2D] = []
    for new_idx, old_idx in enumerate(sorted(used_indices)):
        index_map[old_idx] = new_idx
        new_points.append(points[old_idx])

    remapped_edges = [Edge(index_map[i], index_map[j]) for (i, j) in candidate_edges]
    return new_points, remapped_edges


def compute_closed_polyline(  # noqa: PLR0913
    points: Sequence[Point2D],
    edges: Sequence[Edge],
    leftmost_polyline: int,
    rightmost_polyline: int,
    leftmost_bottom_point: Point2D,
    rightmost_bottom_point: Point2D,
) -> tuple[list[Point2D], list[Edge]]:
    """Compute a closed polyline by adding bottom connecting edges."""
    new_points = list(points)
    new_points.extend([leftmost_bottom_point, rightmost_bottom_point])
    new_edges = list(edges)
    new_edges.extend(
        [
            Edge(len(new_points) - 2, leftmost_polyline),
            Edge(len(new_points) - 1, rightmost_polyline),
            Edge(len(new_points) - 2, len(new_points) - 1),
        ]
    )
    return new_points, new_edges


def remove_isolated_points(
    points: Sequence[Point2D], edges: Sequence[Edge]
) -> tuple[list[Point2D], list[Edge]]:
    """Remove points that are not referenced by any edge."""
    used_indices = {index for edge in edges for index in edge.as_tuple()}

    index_map = {}
    new_points: list[Point2D] = []
    for new_i, old_i in enumerate(sorted(used_indices)):
        index_map[old_i] = new_i
        new_points.append(points[old_i])

    new_edges = [Edge(index_map[edge.start], index_map[edge.end]) for edge in edges]

    return new_points, new_edges


def merge_polygons(
    points1: Sequence[Point2D],
    edges1: Sequence[Edge],
    points2: Sequence[Point2D],
    edges2: Sequence[Edge],
    epsilon: float = 1e-6,
) -> tuple[list[Point2D], list[Edge]]:
    """Merge two polygons, deduplicating close points."""

    def points_are_close(p1: Point2D, p2: Point2D, eps: float = epsilon) -> bool:
        return abs(p1.x - p2.x) <= eps and abs(p1.y - p2.y) <= eps

    merged_points = list(points1)
    merged_edges: set[tuple[int, int]] = set()

    # Normalize edges from poly1
    for edge in edges1:
        merged_edges.add(edge.sorted().as_tuple())

    index_map: dict[int, int] = {}
    for i, p2 in enumerate(points2):
        found = None
        for j, p1 in enumerate(merged_points):
            if points_are_close(p1, p2, epsilon):
                found = j
                break
        if found is not None:
            index_map[i] = found
        else:
            index_map[i] = len(merged_points)
            merged_points.append(p2)

    for edge in edges2:
        ni, nj = index_map[edge.start], index_map[edge.end]
        # An input edge can collapse when its endpoints both match the same
        # existing junction within ``epsilon``. It carries no topology after
        # merging and must not become a zero-length PSLG segment.
        if ni == nj:
            continue
        merged_edges.add((min(ni, nj), max(ni, nj)))

    return merged_points, [Edge(i, j) for i, j in merged_edges]


def remove_coincident(
    points: Sequence[Point2D], edges: Sequence[Edge]
) -> tuple[list[Point2D], list[Edge]]:
    """Remove duplicate points and remap edges."""
    index_map: dict[int, int] = {}
    new_points: list[Point2D] = []
    for i, p in enumerate(points):
        if p in new_points:
            index_map[i] = new_points.index(p)
            continue
        index_map[i] = len(new_points)
        new_points.append(p)

    new_edges: list[Edge] = []
    for edge in edges:
        new_i, new_j = index_map[edge.start], index_map[edge.end]
        if new_i == new_j:
            continue
        new_edge = Edge(min(new_i, new_j), max(new_i, new_j))
        new_edges.append(new_edge)
    return new_points, new_edges


def centroid(points: Sequence[Point2D]) -> Point2D:
    """Compute the centroid of a set of points."""
    n = len(points)
    cx = sum(point.x for point in points) / n
    cy = sum(point.y for point in points) / n
    return Point2D(cx, cy)


def sampling(
    points: Sequence[Point2D],
    edges: Sequence[Edge],
    max_attempts: int = 10000,
    rng: RandomSource | None = None,
) -> Point2D:
    """Sample a point inside a polygon, failing after ``max_attempts``."""
    rng = rng or cast("RandomSource", random)

    def bounding_box(
        points: Sequence[Point2D],
    ) -> tuple[Point2D, Point2D]:
        x0, y0 = points[0].x, points[0].y
        x1, y1 = points[0].x, points[0].y
        for point in points:
            x0 = min(x0, point.x)
            y0 = min(y0, point.y)
            x1 = max(x1, point.x)
            y1 = max(y1, point.y)
        return Point2D(x0, y0), Point2D(x1, y1)

    bbp1, bbp2 = bounding_box(points)
    x = rng.uniform(bbp1.x, bbp2.x)
    y = rng.uniform(bbp1.y, bbp2.y)
    p = Point2D(x, y)
    attempts = 0
    while not point_in_polygon(p, points, edges) and attempts < max_attempts:
        x = rng.uniform(bbp1.x, bbp2.x)
        y = rng.uniform(bbp1.y, bbp2.y)
        p = Point2D(x, y)
        attempts += 1
    if attempts >= max_attempts:
        msg = "Could not sample a point inside the polygon."
        raise RuntimeError(msg)
    return p


def point_in_polygon(
    pt: Point2D,
    points: Sequence[Point2D],
    edges: Sequence[Edge],
) -> bool:
    """Check if a point is inside a polygon using ray casting."""
    x, y = pt.x, pt.y
    inside = False
    for edge in edges:
        p0 = points[edge.start]
        p1 = points[edge.end]
        x0, y0 = p0.x, p0.y
        x1, y1 = p1.x, p1.y
        if ((y0 > y) != (y1 > y)) and (x < (x1 - x0) * (y - y0) / (y1 - y0) + x0):
            inside = not inside
    return inside


def constrained_sampling(  # noqa: PLR0913
    points: Sequence[Point2D],
    edges: Sequence[Edge],
    other_points: Sequence[Point2D],
    other_edges: Sequence[Edge],
    max_attempts: int = 10000,
    rng: RandomSource | None = None,
) -> Point2D:
    """Sample inside the first polygon and outside the second."""
    rng = rng or cast("RandomSource", random)

    def bounding_box(
        points: Sequence[Point2D],
    ) -> tuple[Point2D, Point2D]:
        x0, y0 = points[0].x, points[0].y
        x1, y1 = points[0].x, points[0].y
        for point in points:
            x0 = min(x0, point.x)
            y0 = min(y0, point.y)
            x1 = max(x1, point.x)
            y1 = max(y1, point.y)
        return Point2D(x0, y0), Point2D(x1, y1)

    bbp1, bbp2 = bounding_box(points)
    x = rng.uniform(bbp1.x, bbp2.x)
    y = rng.uniform(bbp1.y, bbp2.y)
    p = Point2D(x, y)
    attempts = 0
    while (
        not point_in_polygon(p, points, edges)
        or point_in_polygon(p, other_points, other_edges)
    ) and attempts < max_attempts:
        x = rng.uniform(bbp1.x, bbp2.x)
        y = rng.uniform(bbp1.y, bbp2.y)
        p = Point2D(x, y)
        attempts += 1
    if attempts >= max_attempts:
        msg = "Could not sample a point satisfying polygon constraints."
        raise RuntimeError(msg)
    return p


def get_region_attribute_points(
    polygons: list[tuple[list[Point2D], list[Edge]]],
    max_attempts: int = 1000,
) -> list[tuple[Point2D, int]]:
    """Generate sample points for each material region between interfaces."""
    if not polygons:
        return []

    attributes: list[tuple[Point2D, int]] = []

    # Region 1: Inside innermost polygon
    innermost_points, innermost_edges = polygons[0]
    try:
        p = sampling(innermost_points, innermost_edges, max_attempts)
        attributes.append((p, 1))
    except RuntimeError:
        # Fall back to centroid
        p = centroid(innermost_points)
        attributes.append((p, 1))

    # Regions 2 to N: Between consecutive polygons
    for i in range(1, len(polygons)):
        outer_points, outer_edges = polygons[i]
        inner_points, inner_edges = polygons[i - 1]

        # Try constrained sampling
        p = constrained_sampling(
            outer_points,
            outer_edges,
            inner_points,
            inner_edges,
            max_attempts,
        )

        attributes.append((p, i + 1))

    return attributes


def connect_ends(
    points: Sequence[Point2D],
    edges: Sequence[Edge],
    lbp: Point2D,
    rbp: Point2D,
) -> tuple[list[Point2D], list[Edge]]:
    """Connect dangling edge endpoints to form a closed shape."""
    points = list(points)
    edges = list(edges)
    counter: defaultdict[int, int] = defaultdict(int)
    for edge in edges:
        counter[edge.start] += 1
        counter[edge.end] += 1
    ends = [point for point, count in counter.items() if count == 1]
    if len(ends) == 4:
        edges.extend([Edge(ends[0], ends[2]), Edge(ends[1], ends[3])])
    if len(ends) == 2:
        points.append(lbp)
        l_id = len(points) - 1

        points.append(rbp)
        r_id = len(points) - 1
        edges.extend(
            [
                Edge(ends[0], l_id),
                Edge(l_id, r_id),
                Edge(r_id, ends[1]),
            ]
        )
    return points, edges


def connect_all_ends(
    points: Sequence[Point2D],
    edges: Sequence[Edge],
    lbp: Point2D,
    rbp: Point2D,
) -> tuple[list[Point2D], list[Edge]]:
    """Connect all dangling endpoints to form a closed shape with bottom edge."""
    points = list(points)
    edges = list(edges)
    counter: defaultdict[int, int] = defaultdict(int)
    for edge in edges:
        counter[edge.start] += 1
        counter[edge.end] += 1
    ends = [point for point, count in counter.items() if count == 1]

    points.append(lbp)
    l_id = len(points) - 1

    points.append(rbp)
    r_id = len(points) - 1

    edges.append(Edge(l_id, r_id))
    ends.extend([l_id, r_id])

    positive_ends = [e for e in ends if points[e].x > 0.0]
    positive_ends.sort(key=lambda e: points[e].y)
    negative_ends = [e for e in ends if points[e].x < 0.0]
    negative_ends.sort(key=lambda e: points[e].y)
    for end_group in [positive_ends, negative_ends]:
        for i, e in enumerate(end_group[:-1]):
            edges.append(Edge(e, end_group[i + 1]))

    return points, edges


def connect_prev(
    points: Sequence[Point2D],
    edges: Sequence[Edge],
    rightmost_point: Point2D,
    leftmost_point: Point2D,
) -> tuple[list[Point2D], list[Edge]]:
    """Connect polygon ends to leftmost and rightmost bottom points."""
    points = list(points)
    edges = list(edges)
    sorted_points = sorted(points)
    first, last = sorted_points[0], sorted_points[-1]
    new_points = points[:]
    new_edges = edges[:]

    if leftmost_point in new_points:
        leftmost_idx = new_points.index(leftmost_point)
    else:
        leftmost_idx = len(new_points)
        new_points.append(leftmost_point)

    if rightmost_point in new_points:
        rightmost_idx = new_points.index(rightmost_point)
    else:
        rightmost_idx = len(new_points)
        new_points.append(rightmost_point)

    new_edges.append(Edge(leftmost_idx, rightmost_idx))
    first_idx = points.index(first)
    last_idx = points.index(last)
    new_edges.append(Edge(leftmost_idx, first_idx))
    new_edges.append(Edge(rightmost_idx, last_idx))
    return new_points, new_edges


def is_closed(_points: Sequence[Point2D], edges: Sequence[Edge]) -> bool:
    """Check if a polygon is closed (all points have degree 2)."""
    point_counter: defaultdict[int, int] = defaultdict(int)
    for edge in edges:
        point_counter[edge.start] += 1
        point_counter[edge.end] += 1
    return all(c == 2 for c in point_counter.values())
