"""Tests for 2D material detection."""

from lsmesher import geometry_2d as g2d
from lsmesher.geometry_types import Edge, Point2D


def test_nested_polygons_get_distinct_region_points() -> None:
    """Region points identify the inner square and surrounding outer region."""
    inner_points = [
        Point2D(0, 0),
        Point2D(1, 0),
        Point2D(1, 1),
        Point2D(0, 1),
    ]
    inner_edges = [Edge(0, 1), Edge(1, 2), Edge(2, 3), Edge(3, 0)]
    outer_points = [
        Point2D(-1, -1),
        Point2D(2, -1),
        Point2D(2, 2),
        Point2D(-1, 2),
    ]
    outer_edges = [Edge(0, 1), Edge(1, 2), Edge(2, 3), Edge(3, 0)]

    attributes = g2d.get_region_attribute_points(
        [(inner_points, inner_edges), (outer_points, outer_edges)]
    )

    assert len(attributes) == 2
    inner_region, outer_region = (point for point, _attribute in attributes)
    assert g2d.point_in_polygon(inner_region, inner_points, inner_edges)
    assert g2d.point_in_polygon(outer_region, outer_points, outer_edges)
    assert not g2d.point_in_polygon(outer_region, inner_points, inner_edges)
