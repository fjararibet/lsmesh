"""Composable 2D mesh pipeline functions."""

from __future__ import annotations

import random
from bisect import bisect_right
from collections import Counter
from itertools import pairwise
from typing import TYPE_CHECKING, Protocol

from lsmesh import geometry_2d as geometry2d
from lsmesh.geometry_types import Edge, Point2D
from lsmesh.pipeline_types import Geometry2D, Layer2D
from lsmesh.polygon_io_2d import (
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
    """Close wall-ending contours, extending only the lowest one to the floor.

    Several disconnected curves may end on each side wall. Pairing their ends
    from the top closes upper islands; an unpaired bottom end on each wall
    belongs to the substrate-spanning curve and needs the common floor.
    """
    if geometry2d.is_closed(layer.points, layer.edges):
        return layer
    points, edges = list(layer.points), list(layer.edges)
    degree = Counter(index for edge in edges for index in edge.as_tuple())
    ends = [index for index, count in degree.items() if count == 1]
    width = rightmost_point.x - leftmost_point.x
    tolerance = max(abs(width) * 1e-9, 1e-12)
    left = sorted(
        (
            index
            for index in ends
            if abs(points[index].x - leftmost_point.x) <= tolerance
        ),
        key=lambda index: points[index].y,
        reverse=True,
    )
    right = sorted(
        (
            index
            for index in ends
            if abs(points[index].x - rightmost_point.x) <= tolerance
        ),
        key=lambda index: points[index].y,
        reverse=True,
    )
    if len(left) + len(right) != len(ends) or len(left) % 2 != len(right) % 2:
        msg = "Cannot close 2D interface: unmatched or off-wall endpoints"
        raise ValueError(msg)
    for group in (left, right):
        paired = group[:-1] if len(group) % 2 else group
        for first, second in zip(paired[0::2], paired[1::2], strict=True):
            edges.append(Edge(first, second))
    if len(left) % 2:
        left_bottom = len(points)
        points.append(leftmost_point)
        right_bottom = len(points)
        points.append(rightmost_point)
        edges.extend(
            (
                Edge(left_bottom, right_bottom),
                Edge(left_bottom, left[-1]),
                Edge(right_bottom, right[-1]),
            )
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


def _crossing_sweep(
    points: Sequence[Point2D],
    edges: Sequence[Edge],
    heights: Sequence[float],
) -> list[list[float]]:
    """Return sorted x-crossings of a polygon for each increasing scan height.

    Scan heights never coincide with vertex heights, so an edge crosses the
    scan line exactly when the height lies strictly inside its y-span. The
    crossing uses the same float expression as
    :func:`lsmesh.geometry_2d.point_in_polygon` so parity checks stay
    bit-identical.
    """
    spans: list[tuple[float, float, Point2D, Point2D]] = []
    for edge in edges:
        start = points[edge.start]
        end = points[edge.end]
        low = min(start.y, end.y)
        high = max(start.y, end.y)
        if high > low:
            spans.append((low, high, start, end))
    spans.sort(key=lambda span: span[0])
    crossings: list[list[float]] = []
    active: list[tuple[float, float, Point2D, Point2D]] = []
    next_span = 0
    for y in heights:
        while next_span < len(spans) and spans[next_span][0] < y:
            active.append(spans[next_span])
            next_span += 1
        active = [span for span in active if span[1] > y]
        result: list[float] = []
        for _low, _high, start, end in active:
            if (start.y > y) == (end.y > y):
                continue
            result.append(
                start.x + (end.x - start.x) * (y - start.y) / (end.y - start.y)
            )
        result.sort()
        crossings.append(result)
    return crossings


def _region_seed_candidates(  # noqa: C901, PLR0915
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
    bands: list[tuple[float, list[tuple[float, float, Point2D]]]] = []

    band_heights = [
        (lower + upper) / 2 for lower, upper in pairwise(y_values) if upper > lower
    ]
    layer_crossings = _crossing_sweep(layer.points, layer.edges, band_heights)
    comparison_crossings = (
        _crossing_sweep(comparison.points, comparison.edges, band_heights)
        if comparison is not None
        else None
    )

    for band_index, y in enumerate(band_heights):
        layer_xs = layer_crossings[band_index]
        comparison_xs = (
            comparison_crossings[band_index]
            if comparison_crossings is not None
            else None
        )
        x_values = list(layer_xs)
        if comparison_xs is not None:
            x_values.extend(comparison_xs)
        unique_x = sorted(set(x_values))
        band: list[tuple[float, float, Point2D]] = []
        for left, right in pairwise(unique_x):
            if right <= left:
                continue
            point = Point2D((left + right) / 2, y)
            # Parity of crossings right of the midpoint matches
            # point_in_polygon ray casting without the per-candidate scan.
            inside_layer = (len(layer_xs) - bisect_right(layer_xs, point.x)) % 2 == 1
            if not inside_layer:
                continue
            if (
                comparison_xs is not None
                and (len(comparison_xs) - bisect_right(comparison_xs, point.x)) % 2 == 1
            ):
                continue
            band.append((left, right, point))
        # Keep empty bands: they are topological gaps and must prevent the
        # union step below from joining components across empty space.
        bands.append((y, band))

    intervals = [interval for _y, band in bands for interval in band]
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

    def union_overlapping(
        previous_band: Sequence[tuple[float, float, Point2D]],
        current_band: Sequence[tuple[float, float, Point2D]],
    ) -> None:
        # Interval lists are disjoint and sorted, so a two-pointer sweep finds
        # every overlapping pair without the quadratic cross product.
        first = second = 0
        while first < len(previous_band) and second < len(current_band):
            left_interval = previous_band[first]
            right_interval = current_band[second]
            if min(left_interval[1], right_interval[1]) > max(
                left_interval[0], right_interval[0]
            ):
                union(indices[id(left_interval)], indices[id(right_interval)])
            if left_interval[1] < right_interval[1]:
                first += 1
            else:
                second += 1

    for (_y, previous_band), (_y2, current_band) in pairwise(bands):
        union_overlapping(previous_band, current_band)

    widest_by_component: dict[int, tuple[float, Point2D]] = {}
    for index, (left, right, point) in enumerate(intervals):
        root = find(index)
        candidate = (right - left, point)
        if (
            root not in widest_by_component
            or candidate[0] > widest_by_component[root][0]
        ):
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
    if material_ids is not None and len(material_ids) != len(closed_layers):
        msg = "ViennaPS material count does not match the number of 2D level sets"
        raise ValueError(msg)
    attributes, attribute_ids = collect_2d_region_seeds(
        closed_layers,
        original_layers=layers,
        enabled=detect_holes,
        sampler=sampler,
        material_ids=material_ids,
    )
    merged = merge_2d_layers(
        closed_layers,
        attributes=attributes,
        attribute_ids=attribute_ids,
    )
    return simplify_2d_geometry(merged, epsilon=epsilon)


def collect_2d_region_seeds(
    closed_layers: Sequence[Layer2D],
    *,
    original_layers: Sequence[Layer2D],
    enabled: bool,
    sampler: AttributeSampler2D = default_2d_attribute_sampler,
    material_ids: Sequence[int] | None = None,
) -> tuple[tuple[Point2D, ...], tuple[int, ...]]:
    """Place one seed per disconnected material region, retaining material IDs."""
    if not enabled:
        return (), ()
    if len(original_layers) != len(closed_layers) or (
        material_ids is not None and len(material_ids) != len(closed_layers)
    ):
        msg = "2D layers and material IDs must have matching lengths"
        raise ValueError(msg)
    primary_attributes = collect_2d_attributes(
        closed_layers,
        enabled=True,
        sampler=sampler,
        original_layers=original_layers,
    )
    attributes: list[Point2D] = []
    attribute_ids: list[int] = []
    previous: Layer2D | None = None
    for index, (layer, source_layer, primary) in enumerate(
        zip(closed_layers, original_layers, primary_attributes, strict=True)
    ):
        originally_closed = geometry2d.is_closed(
            source_layer.points, source_layer.edges
        )
        candidates = _region_seed_candidates(
            layer, previous, originally_closed=originally_closed
        )
        seeds = candidates or (primary,)
        material_id = material_ids[index] if material_ids is not None else index + 1
        attributes.extend(seeds)
        attribute_ids.extend([material_id] * len(seeds))
        previous = layer
    return tuple(attributes), tuple(attribute_ids)


def geometry_2d_to_poly_text(geometry: Geometry2D) -> str:
    """Serialize merged 2D geometry to Triangle POLY text."""
    return vtp_to_poly_string(
        points=geometry.points,
        edges=geometry.edges,
        attributes=geometry.attributes,
        attribute_ids=geometry.attribute_ids,
    )
