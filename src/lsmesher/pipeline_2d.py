"""Composable 2D mesh pipeline functions."""

from __future__ import annotations

import random
from itertools import pairwise
from typing import TYPE_CHECKING, Protocol

from lsmesher import geometry_2d as geometry2d
from lsmesher.geometry_types import Edge, Point2D
from lsmesher.pipeline_types import Geometry2D, Layer2D
from lsmesher.polygon_io_2d import (
    read_vtp_edges,
    read_vtp_points,
    vtp_to_poly_string,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


class AttributeSampler2D(Protocol):
    """Callable interface for deterministic or random attribute sampling."""

    def __call__(
        self,
        layer: Layer2D,
        previous: Layer2D | None,
        *,
        originally_closed: bool,
    ) -> Point2D:
        """Return an attribute point for one layer."""
        ...


def read_2d_layers(files: Sequence[str | Path]) -> tuple[Layer2D, ...]:
    """Read VTP files into 2D pipeline layers."""
    layers: list[Layer2D] = []
    for file in files:
        points, *_ = read_vtp_points(file)
        edges = read_vtp_edges(file)
        layers.append(Layer2D(tuple(points), tuple(edges)))
    return tuple(layers)


def compute_bottom_points_2d_from_layers(
    layers: Sequence[Layer2D],
) -> tuple[Point2D, Point2D]:
    """Compute bottom closure points from all input layers."""
    all_points = tuple(point for layer in layers for point in layer.points)
    if not all_points:
        msg = "Cannot compute bottom points: no input points."
        raise ValueError(msg)

    y_coords = [point.y for point in all_points]
    min_y_raw = min(y_coords)
    max_y = max(y_coords)
    height = max_y - min_y_raw

    if height == 0:
        msg = (
            "Cannot compute bottom points: all input points have the same Y "
            f"coordinate ({min_y_raw}). The geometry has zero height."
        )
        raise ValueError(msg)

    min_x = min(point.x for point in all_points)
    max_x = max(point.x for point in all_points)
    min_y = min_y_raw - height * 0.10
    return Point2D(min_x, min_y), Point2D(max_x, min_y)


def close_2d_layer(
    layer: Layer2D,
    *,
    leftmost_point: Point2D,
    rightmost_point: Point2D,
) -> Layer2D:
    """Close an open 2D layer using the provided bottom points."""
    if geometry2d.is_closed(layer.points, layer.edges):
        return layer

    points, edges = geometry2d.connect_prev(
        points=layer.points,
        edges=layer.edges,
        rightmost_point=rightmost_point,
        leftmost_point=leftmost_point,
    )
    return Layer2D(tuple(points), tuple(edges))


def close_2d_layers(
    layers: Sequence[Layer2D],
    *,
    leftmost_point: Point2D,
    rightmost_point: Point2D,
) -> tuple[Layer2D, ...]:
    """Close all open 2D layers using shared bottom closure points."""
    return tuple(
        close_2d_layer(
            layer,
            leftmost_point=leftmost_point,
            rightmost_point=rightmost_point,
        )
        for layer in layers
    )


def default_2d_attribute_sampler(
    layer: Layer2D,
    previous: Layer2D | None,
    *,
    originally_closed: bool,
) -> Point2D:
    """Sample a region attribute point with centroid fallback."""
    if previous is not None and not originally_closed:
        try:
            return geometry2d.constrained_sampling(
                layer.points,
                layer.edges,
                previous.points,
                previous.edges,
            )
        except RuntimeError:
            return geometry2d.centroid(layer.points)

    try:
        return geometry2d.sampling(layer.points, layer.edges)
    except RuntimeError:
        return geometry2d.centroid(layer.points)


def seeded_2d_attribute_sampler(seed: int) -> AttributeSampler2D:
    """Create a repeatable region sampler without changing global RNG state."""
    rng = random.Random(seed)  # noqa: S311

    def sample(
        layer: Layer2D,
        previous: Layer2D | None,
        *,
        originally_closed: bool,
    ) -> Point2D:
        if previous is not None and not originally_closed:
            try:
                return geometry2d.constrained_sampling(
                    layer.points,
                    layer.edges,
                    previous.points,
                    previous.edges,
                    rng=rng,
                )
            except RuntimeError:
                return geometry2d.centroid(layer.points)
        try:
            return geometry2d.sampling(layer.points, layer.edges, rng=rng)
        except RuntimeError:
            return geometry2d.centroid(layer.points)

    return sample


def collect_2d_attributes(
    layers: Sequence[Layer2D],
    *,
    enabled: bool,
    sampler: AttributeSampler2D = default_2d_attribute_sampler,
    original_layers: Sequence[Layer2D] | None = None,
) -> tuple[Point2D, ...]:
    """Collect material attribute points for each layer."""
    if not enabled:
        return ()

    source_layers = original_layers or layers
    attributes: list[Point2D] = []
    previous: Layer2D | None = None
    for layer, source_layer in zip(layers, source_layers, strict=True):
        originally_closed = geometry2d.is_closed(
            source_layer.points, source_layer.edges
        )
        attributes.append(
            sampler(layer, previous, originally_closed=originally_closed),
        )
        previous = layer
    return tuple(attributes)


def _region_seed_candidates(  # noqa: C901, PLR0912
    layer: Layer2D,
    previous: Layer2D | None,
    *,
    originally_closed: bool,
) -> tuple[Point2D, ...]:
    """Return seeds for every horizontal component of a material region.

    A single ViennaLS interface can describe a material that is split into
    disconnected regions (oxide on both sides of a fin, for example). Triangle
    propagates a region attribute only within one connected PSLG region, so one
    random point per interface is insufficient.
    """
    comparison = previous if previous is not None and not originally_closed else None
    all_points = (*layer.points, *(comparison.points if comparison is not None else ()))
    y_values = sorted({point.y for point in all_points})
    bands: list[list[tuple[float, float, Point2D]]] = []

    def intersections(candidate_layer: Layer2D, y: float) -> list[float]:
        result: list[float] = []
        for edge in candidate_layer.edges:
            start = candidate_layer.points[edge.start]
            end = candidate_layer.points[edge.end]
            if (start.y > y) == (end.y > y):
                continue
            result.append(start.x + (end.x - start.x) * (y - start.y) / (end.y - start.y))
        return result

    for lower, upper in pairwise(y_values):
        if upper <= lower:
            continue
        y = (lower + upper) / 2
        x_values = intersections(layer, y)
        if comparison is not None:
            x_values.extend(intersections(comparison, y))
        unique_x = sorted(set(x_values))
        band: list[tuple[float, float, Point2D]] = []
        for left, right in pairwise(unique_x):
            if right <= left:
                continue
            point = Point2D((left + right) / 2, y)
            if not geometry2d.point_in_polygon(point, layer.points, layer.edges):
                continue
            if comparison is not None and geometry2d.point_in_polygon(
                point, comparison.points, comparison.edges
            ):
                continue
            band.append((left, right, point))
        # Keep empty bands: they are topological gaps and must prevent the
        # union step below from joining components across empty space.
        bands.append(band)

    intervals = [interval for band in bands for interval in band]
    if not intervals:
        return ()
    indices = {id(interval): index for index, interval in enumerate(intervals)}
    parents = list(range(len(intervals)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(first: int, second: int) -> None:
        first_root, second_root = find(first), find(second)
        if first_root != second_root:
            parents[second_root] = first_root

    for previous_band, current_band in pairwise(bands):
        for first in previous_band:
            for second in current_band:
                if min(first[1], second[1]) > max(first[0], second[0]):
                    union(indices[id(first)], indices[id(second)])

    widest_by_component: dict[int, tuple[float, Point2D]] = {}
    for index, (left, right, point) in enumerate(intervals):
        root = find(index)
        candidate = (right - left, point)
        if root not in widest_by_component or candidate[0] > widest_by_component[root][0]:
            widest_by_component[root] = candidate
    return tuple(candidate[1] for candidate in widest_by_component.values())


def merge_2d_layers(
    layers: Sequence[Layer2D],
    *,
    attributes: Sequence[Point2D] = (),
    attribute_ids: Sequence[int] = (),
) -> Geometry2D:
    """Merge 2D layers into a single geometry."""
    merged_points: list[Point2D] = []
    merged_edges: list[Edge] = []
    for layer in layers:
        merged_points, merged_edges = geometry2d.merge_polygons(
            points1=merged_points,
            edges1=merged_edges,
            points2=layer.points,
            edges2=layer.edges,
        )
    return Geometry2D(
        points=tuple(merged_points),
        edges=tuple(merged_edges),
        attributes=tuple(attributes),
        attribute_ids=tuple(attribute_ids),
    )


def simplify_2d_geometry(geometry: Geometry2D, *, epsilon: float) -> Geometry2D:
    """Remove collinear points from merged 2D geometry."""
    points, edges = geometry2d.remove_collinear(
        geometry.points,
        geometry.edges,
        epsilon,
    )
    return Geometry2D(
        points=tuple(points),
        edges=tuple(edges),
        attributes=geometry.attributes,
        attribute_ids=geometry.attribute_ids,
    )


def build_2d_poly_geometry(
    layers: Sequence[Layer2D],
    *,
    epsilon: float,
    detect_holes: bool,
    sampler: AttributeSampler2D = default_2d_attribute_sampler,
    material_ids: Sequence[int] | None = None,
) -> Geometry2D:
    """Build merged 2D geometry from layers using pure transformation steps."""
    leftmost, rightmost = compute_bottom_points_2d_from_layers(layers)
    closed_layers = close_2d_layers(
        layers,
        leftmost_point=leftmost,
        rightmost_point=rightmost,
    )
    primary_attributes = collect_2d_attributes(
        closed_layers,
        enabled=detect_holes,
        sampler=sampler,
        original_layers=layers,
    )
    if material_ids is not None and len(material_ids) != len(closed_layers):
        msg = "ViennaPS material count does not match the number of 2D level sets"
        raise ValueError(msg)
    attributes: list[Point2D] = []
    attribute_ids: list[int] = []
    previous: Layer2D | None = None
    if detect_holes:
        for index, (layer, source_layer, primary) in enumerate(
            zip(closed_layers, layers, primary_attributes, strict=True)
        ):
            candidates = _region_seed_candidates(
                layer,
                previous,
                originally_closed=geometry2d.is_closed(
                    source_layer.points, source_layer.edges
                ),
            )
            seeds = candidates or (primary,)
            material_id = material_ids[index] if material_ids is not None else index + 1
            attributes.extend(seeds)
            attribute_ids.extend([material_id] * len(seeds))
            previous = layer
    merged = merge_2d_layers(
        closed_layers,
        attributes=attributes,
        attribute_ids=attribute_ids,
    )
    return simplify_2d_geometry(merged, epsilon=epsilon)


def geometry_2d_to_poly_text(geometry: Geometry2D) -> str:
    """Serialize merged 2D geometry to Triangle POLY text."""
    return vtp_to_poly_string(
        points=geometry.points,
        edges=geometry.edges,
        attributes=geometry.attributes,
        attribute_ids=geometry.attribute_ids,
    )
