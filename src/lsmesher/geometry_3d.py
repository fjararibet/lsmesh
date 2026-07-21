"""3D geometry utilities for solid mesh processing."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from scipy.spatial import KDTree

from lsmesher.geometry_types import (
    Edge,
    Face,
    Point2D,
    Point3D,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


def triangle_area(
    p1: Point3D,
    p2: Point3D,
    p3: Point3D,
) -> float:
    """Compute the area of a triangle in 3D space."""
    v1 = (p2.x - p1.x, p2.y - p1.y, p2.z - p1.z)
    v2 = (p3.x - p1.x, p3.y - p1.y, p3.z - p1.z)
    cross_product = (
        v1[1] * v2[2] - v1[2] * v2[1],
        v1[2] * v2[0] - v1[0] * v2[2],
        v1[0] * v2[1] - v1[1] * v2[0],
    )
    return 0.5 * math.sqrt(
        cross_product[0] ** 2 + cross_product[1] ** 2 + cross_product[2] ** 2
    )


def remove_collinear(
    points: Sequence[Point3D],
    edges: Sequence[Edge],
    epsilon: float = 1e-3,
) -> tuple[list[Point3D], list[Edge]]:
    """Remove collinear points from a 3D polyline."""
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
            ki = [p for p in adjacency[i] if p != j]
            ki = ki[0] if ki else None
            kj = [p for p in adjacency[j] if p != i]
            kj = kj[0] if kj else None
            if (
                ki is not None
                and triangle_area(points[i], points[j], points[ki]) <= epsilon
            ):
                candidate_edges.discard(tuple(sorted((ki, i))))
                candidate_edges.discard(tuple(sorted((i, j))))
                candidate_edges.add(tuple(sorted((ki, j))))
                done = False
                break
            if (
                kj is not None
                and triangle_area(points[i], points[j], points[kj]) <= epsilon
            ):
                candidate_edges.discard(tuple(sorted((i, j))))
                candidate_edges.discard(tuple(sorted((j, kj))))
                candidate_edges.add(tuple(sorted((i, kj))))
                done = False
                break

    used_indices = {i for e in candidate_edges for i in e}

    index_map = {}
    new_points: list[Point3D] = []
    for new_idx, old_idx in enumerate(sorted(used_indices)):
        index_map[old_idx] = new_idx
        new_points.append(points[old_idx])

    remapped_edges = [Edge(index_map[i], index_map[j]) for (i, j) in candidate_edges]
    return new_points, remapped_edges


def compute_closed_polyline(  # noqa: PLR0913
    points: Sequence[Point3D],
    edges: Sequence[Edge],
    leftmost_polyline: int,
    rightmost_polyline: int,
    leftmost_bottom_point: Point3D,
    rightmost_bottom_point: Point3D,
) -> tuple[list[Point3D], list[Edge]]:
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
    points: Sequence[Point3D], edges: Sequence[Edge]
) -> tuple[list[Point3D], list[Edge]]:
    """Remove points not referenced by any edge."""
    used_indices = {index for edge in edges for index in edge.as_tuple()}

    index_map = {}
    new_points: list[Point3D] = []
    for new_i, old_i in enumerate(sorted(used_indices)):
        index_map[old_i] = new_i
        new_points.append(points[old_i])

    new_edges = [Edge(index_map[edge.start], index_map[edge.end]) for edge in edges]

    return new_points, new_edges


def merge_solid(
    points1: Sequence[Point3D],
    faces1: Sequence[Face],
    points2: Sequence[Point3D],
    faces2: Sequence[Face],
    epsilon: float = 1e-6,
) -> tuple[list[Point3D], list[Face]]:
    """Merge two OFF-style meshes, deduplicating close points and faces."""

    def points_are_close(
        p1: Point3D,
        p2: Point3D,
        eps: float = epsilon,
    ) -> bool:
        return (
            abs(p1.x - p2.x) <= eps
            and abs(p1.y - p2.y) <= eps
            and abs(p1.z - p2.z) <= eps
        )

    merged_points = list(points1)
    index_map: dict[int, int] = {}

    # Map points2 to merged indices
    for i, p2 in enumerate(points2):
        found = None
        for j, p1 in enumerate(merged_points):
            if points_are_close(p1, p2):
                found = j
                break

        if found is not None:
            index_map[i] = found
        else:
            index_map[i] = len(merged_points)
            merged_points.append(p2)

    # Deduplicate faces using a set of normalized (sorted) tuples
    merged_faces_set: set[tuple[int, ...]] = set()

    # Add faces from mesh1
    for face in faces1:
        merged_faces_set.add(tuple(sorted(face.vertices)))

    # Add faces from mesh2 (with remapped indices)
    for face in faces2:
        remapped = [index_map[i] for i in face.vertices]
        merged_faces_set.add(tuple(sorted(remapped)))

    # Convert back to list of lists
    merged_faces = [Face(face) for face in merged_faces_set]

    return merged_points, merged_faces


def merge_solid_quick(
    points1: Sequence[Point3D],
    faces1: Sequence[Face],
    points2: Sequence[Point3D],
    faces2: Sequence[Face],
    epsilon: float = 1e-6,
) -> tuple[list[Point3D], list[Face]]:
    """Merge two OFF-style meshes quickly using KDTree for point deduplication."""
    # Convert to numpy arrays
    pts1 = np.array([point.as_tuple() for point in points1], dtype=np.float64)
    pts2 = np.array([point.as_tuple() for point in points2], dtype=np.float64)

    # Build KDTree for points1
    if len(pts1) > 0:
        tree = KDTree(pts1)
        # Query all points2 at once
        dist, idx = tree.query(pts2, distance_upper_bound=epsilon)
        # For unmatched points (distance = inf), add them to the merged array
        unmatched_mask = np.isinf(dist)
    else:
        # If points1 empty, all points2 are unmatched
        unmatched_mask = np.ones(len(pts2), dtype=bool)
        idx = np.arange(len(pts2))

    # Prepare merged points
    new_points = pts2[unmatched_mask]
    merged_points_arr = np.vstack([pts1, new_points]) if len(pts1) else new_points

    # Build index map from points2 to merged indices
    index_map_arr = np.empty(len(pts2), dtype=int)
    next_index = len(pts1)
    for i, is_unmatched in enumerate(unmatched_mask):
        if is_unmatched:
            index_map_arr[i] = next_index
            next_index += 1
        else:
            index_map_arr[i] = int(idx[i])

    # Deduplicate faces (unordered)
    merged_faces_set: set[tuple[int, ...]] = set()

    # Add faces from mesh1
    for face in faces1:
        merged_faces_set.add(tuple(sorted(face.vertices)))

    # Add faces from mesh2 (remapped)
    for face in faces2:
        remapped = tuple(sorted(index_map_arr[np.array(face.vertices, dtype=int)]))
        merged_faces_set.add(remapped)

    # Convert back to list form
    merged_faces = [Face(face) for face in merged_faces_set]
    merged_points = [
        Point3D(float(x), float(y), float(z)) for x, y, z in merged_points_arr.tolist()
    ]

    return merged_points, merged_faces


def merge_polygons_quick(
    points1: Sequence[Point2D],
    edges1: Sequence[Edge],
    points2: Sequence[Point2D],
    edges2: Sequence[Edge],
    epsilon: float = 1e-6,
) -> tuple[list[Point2D], list[Edge]]:
    """Merge two 2D polygons quickly using KDTree."""
    points1_arr = np.asarray([point.as_tuple() for point in points1])
    points2_arr = np.asarray([point.as_tuple() for point in points2])
    merged_points = list(points1)

    # Build KDTree for all points1
    if len(points1_arr) > 0:
        tree = KDTree(points1_arr)
        _dists, idxs = tree.query(points2_arr, distance_upper_bound=epsilon)
        # idxs == len(points1) means "no match" (outside search radius)
        found_mask = idxs < len(points1_arr)
    else:
        idxs = np.full(len(points2_arr), fill_value=len(points1_arr))
        found_mask = np.zeros(len(points2_arr), dtype=bool)

    # Build index_map vectorized
    index_map_arr = np.empty(len(points2_arr), dtype=int)
    index_map_arr[found_mask] = idxs[found_mask]
    # Add unmatched points
    unmatched = np.nonzero(~found_mask)[0]
    new_indices = np.arange(len(merged_points), len(merged_points) + len(unmatched))
    index_map_arr[unmatched] = new_indices
    merged_points.extend(
        Point2D(float(x), float(y)) for x, y in points2_arr[unmatched].tolist()
    )

    # Merge edges
    merged_edges: set[tuple[int, int]] = {edge.sorted().as_tuple() for edge in edges1}
    for edge in edges2:
        ni, nj = int(index_map_arr[edge.start]), int(index_map_arr[edge.end])
        merged_edges.add((min(ni, nj), max(ni, nj)))

    return merged_points, [Edge(i, j) for i, j in merged_edges]


def remove_coincident(
    points: Sequence[Point3D], edges: Sequence[Edge]
) -> tuple[list[Point3D], list[Edge]]:
    """Remove duplicate points and remap edges."""
    index_map: dict[int, int] = {}
    new_points: list[Point3D] = []
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


def centroid(
    points: Sequence[Point3D],
) -> Point3D:
    """Compute the centroid of a set of 3D points."""
    n = len(points)
    cx = sum(point.x for point in points) / n
    cy = sum(point.y for point in points) / n
    cz = sum(point.z for point in points) / n
    return Point3D(cx, cy, cz)


def sampling(points: Sequence[Point3D], edges: Sequence[Edge]) -> Point3D:
    """Sample a random point inside a 3D polyhedron using rejection sampling."""

    def point_in_polygon(
        pt: Point3D,
        points: Sequence[Point3D],
        edges: Sequence[Edge],
    ) -> bool:
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

    def bounding_box(
        points: Sequence[Point3D],
    ) -> tuple[Point3D, Point3D]:
        x0, y0, z0 = points[0].as_tuple()
        x1, y1, z1 = points[0].as_tuple()
        for point in points:
            x0 = min(x0, point.x)
            y0 = min(y0, point.y)
            z0 = min(z0, point.z)
            x1 = max(x1, point.x)
            y1 = max(y1, point.y)
            z1 = max(z1, point.z)
        return Point3D(x0, y0, z0), Point3D(x1, y1, z1)

    bbp1, bbp2 = bounding_box(points)
    x = random.uniform(bbp1.x, bbp2.x)  # noqa: S311
    y = random.uniform(bbp1.y, bbp2.y)  # noqa: S311
    z = random.uniform(bbp1.z, bbp2.z)  # noqa: S311
    p = Point3D(x, y, z)
    while not point_in_polygon(p, points, edges):
        x = random.uniform(bbp1.x, bbp2.x)  # noqa: S311
        y = random.uniform(bbp1.y, bbp2.y)  # noqa: S311
        z = random.uniform(bbp1.z, bbp2.z)  # noqa: S311
        p = Point3D(x, y, z)
    return p


def connect_ends(
    points: Sequence[Point3D],
    edges: Sequence[Edge],
    lbp: Point3D,
    rbp: Point3D,
) -> tuple[list[Point3D], list[Edge]]:
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
    points: Sequence[Point3D],
    edges: Sequence[Edge],
    lbp: Point3D,
    rbp: Point3D,
) -> tuple[list[Point3D], list[Edge]]:
    """Connect all dangling endpoints with a bottom edge."""
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


@dataclass
class PointIdx:
    """A point with its index in a list."""

    point: Point3D
    idx: int


def close_solid(
    points: Sequence[Point3D],
    faces: Sequence[Face],
    border_points: Sequence[Point3D],
) -> tuple[list[Point3D], list[Face]]:
    """Close a solid mesh by adding faces to connect border points."""
    new_points = list(points)
    new_faces = list(faces)

    border_points_idx = [
        PointIdx(point=border_points[i], idx=len(points) + i)
        for i in range(len(border_points))
    ]
    new_points.extend(border_points)
    for i, curr in enumerate(border_points_idx):
        next_pt = border_points_idx[(i + 1) % len(border_points_idx)]
        close_points = []
        match = "x" if abs(curr.point.x - next_pt.point.x) < 10e-6 else "y"
        for j, p in enumerate(points):
            dist = {
                "x": abs(p.x - curr.point.x),
                "y": abs(p.y - curr.point.y),
            }
            if dist[match] < 10e-6:
                close_points.append(PointIdx(point=p, idx=j))
        ordering_keys = {
            "x": lambda p: p.point.y,
            "y": lambda p: p.point.x,
        }
        close_points = sorted(close_points, key=ordering_keys[match])
        new_face = (
            [min(curr, next_pt, key=ordering_keys[match]).idx]
            + [p.idx for p in close_points]
            + [max(curr, next_pt, key=ordering_keys[match]).idx]
        )
        new_faces.append(Face(tuple(new_face)))

    new_faces.append(Face(tuple(p.idx for p in border_points_idx)))
    return new_points, new_faces
