"""Composable 2D mesh pipeline functions."""

from __future__ import annotations

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
        originally_closed = geometry2d.is_closed(source_layer.points, source_layer.edges)
        attributes.append(
            sampler(layer, previous, originally_closed=originally_closed),
        )
        previous = layer
    return tuple(attributes)


def merge_2d_layers(
    layers: Sequence[Layer2D],
    *,
    attributes: Sequence[Point2D] = (),
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
    )


def build_2d_poly_geometry(
    layers: Sequence[Layer2D],
    *,
    epsilon: float,
    detect_holes: bool,
    sampler: AttributeSampler2D = default_2d_attribute_sampler,
) -> Geometry2D:
    """Build merged 2D geometry from layers using pure transformation steps."""
    leftmost, rightmost = compute_bottom_points_2d_from_layers(layers)
    closed_layers = close_2d_layers(
        layers,
        leftmost_point=leftmost,
        rightmost_point=rightmost,
    )
    attributes = collect_2d_attributes(
        closed_layers,
        enabled=detect_holes,
        sampler=sampler,
        original_layers=layers,
    )
    merged = merge_2d_layers(closed_layers, attributes=attributes)
    return simplify_2d_geometry(merged, epsilon=epsilon)


def geometry_2d_to_poly_text(geometry: Geometry2D) -> str:
    """Serialize merged 2D geometry to Triangle POLY text."""
    return vtp_to_poly_string(
        points=geometry.points,
        edges=geometry.edges,
        attributes=geometry.attributes,
    )
