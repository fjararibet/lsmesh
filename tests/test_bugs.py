"""Regression tests for bugs fixed in geometry processing."""

import pytest

# Import from the new lsmesher package
from lsmesher.geometry_2d import connect_prev, constrained_sampling, sampling
from lsmesher.geometry_types import Edge, Point2D


class TestConnectPrevBug:
    """
    KNOWN BUG: connect_prev() creates invalid edge indices

    When leftmost_point or rightmost_point already exist in the points list,
    connect_prev() doesn't add them (good) but still creates edges using
    indices that would have been assigned (bad). This causes IndexError
    when those edges are used later.

    Location: lsmesher/geometry_2d.py
    """

    def test_connect_prev_creates_invalid_edge_indices(self):
        """
        KNOWN BUG: connect_prev() creates edges with indices >= len(points)

        Expected: All edge indices should be < len(points)
        Actual: Edges reference indices that don't exist

        This test documents the bug - it will FAIL until fixed.
        """
        # Create a simple polygon
        points = [
            Point2D(0.0, 0.0),
            Point2D(1.0, 0.0),
            Point2D(1.0, 1.0),
            Point2D(0.0, 1.0),
        ]
        edges = [Edge(0, 1), Edge(1, 2), Edge(2, 3), Edge(3, 0)]

        # These points already exist in the polygon
        rightmost_point = Point2D(1.0, 0.0)  # Already at index 1
        leftmost_point = Point2D(0.0, 0.0)  # Already at index 0

        new_points, new_edges = connect_prev(
            points, edges, rightmost_point, leftmost_point
        )

        # BUG: Some edges have indices >= len(new_points)
        # This assertion will FAIL, documenting the bug
        invalid_edges = [
            edge
            for edge in new_edges
            if edge.start >= len(new_points) or edge.end >= len(new_points)
        ]

        assert len(invalid_edges) == 0, (
            f"BUG: connect_prev() created {len(invalid_edges)} invalid edges: "
            f"{invalid_edges}. Edge indices must be < len(points)={len(new_points)}. "
            f"This happens when leftmost_point or rightmost_point already exist "
            f"in the points list - edges are created for indices that weren't added."
        )


class TestSamplingInfiniteLoopBug:
    """
    KNOWN BUG: sampling() and constrained_sampling() can infinite loop

    When given a degenerate polygon (e.g., a line or single point) with no
    interior area, the random sampling loops forever trying to find a point
    inside the polygon.

    Location: lsmesher/geometry_2d.py

    NOTE: These tests use pytest-timeout to detect infinite loops.
    Install with: uv pip install pytest-timeout
    """

    def test_sampling_infinite_loop_on_degenerate_polygon(self):
        """sampling() raises instead of looping forever on degenerate polygons."""
        # Degenerate polygon - just a line, no interior
        points = [
            Point2D(0.0, 0.0),
            Point2D(1.0, 0.0),
            Point2D(2.0, 0.0),  # All points collinear on x-axis
        ]
        edges = [Edge(0, 1), Edge(1, 2)]

        with pytest.raises(RuntimeError):
            sampling(points, edges, max_attempts=10)

    def test_constrained_sampling_infinite_loop_on_degenerate_polygons(self):
        """constrained_sampling() raises instead of looping forever."""
        # Two degenerate polygons (lines)
        points1 = [Point2D(0.0, 0.0), Point2D(1.0, 0.0), Point2D(2.0, 0.0)]
        edges1 = [Edge(0, 1), Edge(1, 2)]

        points2 = [Point2D(0.0, 1.0), Point2D(1.0, 1.0), Point2D(2.0, 1.0)]
        edges2 = [Edge(0, 1), Edge(1, 2)]

        with pytest.raises(RuntimeError):
            constrained_sampling(points1, edges1, points2, edges2, max_attempts=10)


# NOTE: point_in_polygon is a nested function inside sampling() and constrained_sampling()
# so we can't test it directly. The bug is triggered when connect_prev() creates invalid
# edge indices and those are passed to sampling(), which then crashes with IndexError.
# This is tested indirectly by test_connect_prev_creates_invalid_edge_indices above.
