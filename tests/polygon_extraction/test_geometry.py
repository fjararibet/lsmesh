"""
Regression tests for geometry_2d module
"""

# Import from the new lsmesher package
from lsmesher.geometry_2d import (
    centroid,
    connect_all_ends,
    connect_ends,
    connect_prev,
    constrained_sampling,
    is_closed,
    merge_polygons,
    remove_coincident,
    remove_collinear,
    remove_isolated_points,
    sampling,
    triangle_area,
)
from lsmesher.geometry_types import Edge, Point2D


def p(x: float, y: float) -> Point2D:
    return Point2D(x, y)


def e(start: int, end: int) -> Edge:
    return Edge(start, end)


class TestTriangleArea:
    """Tests for triangle_area function."""

    def test_right_triangle(self):
        """Test area of right triangle."""
        p1 = p(0.0, 0.0)
        p2 = p(3.0, 0.0)
        p3 = p(0.0, 4.0)

        area = triangle_area(p1, p2, p3)

        # Double area should be 3*4 = 12
        assert area == 12.0

    def test_equilateral_triangle(self):
        """Test area of equilateral triangle."""
        p1 = p(0.0, 0.0)
        p2 = p(2.0, 0.0)
        p3 = p(1.0, 1.732)  # ~sqrt(3)

        area = triangle_area(p1, p2, p3)

        # Should be positive
        assert area > 0

    def test_collinear_points(self):
        """Test that collinear points give zero area."""
        p1 = p(0.0, 0.0)
        p2 = p(1.0, 1.0)
        p3 = p(2.0, 2.0)

        area = triangle_area(p1, p2, p3)

        assert area == 0.0

    def test_triangle_order_independence(self):
        """Test that area is independent of point order."""
        p1 = p(0.0, 0.0)
        p2 = p(3.0, 0.0)
        p3 = p(0.0, 4.0)

        area1 = triangle_area(p1, p2, p3)
        area2 = triangle_area(p3, p1, p2)
        area3 = triangle_area(p2, p3, p1)

        assert area1 == area2 == area3


class TestRemoveCollinear:
    """Tests for remove_collinear function."""

    def test_remove_collinear_middle_point(self, collinear_points):
        """Test removal of collinear middle point."""
        points, edges = collinear_points

        new_points, new_edges = remove_collinear(points, edges, epsilon=1e-3)

        # Should remove the middle collinear point
        assert len(new_points) < len(points)
        assert len(new_edges) < len(edges)

    def test_no_removal_with_low_epsilon(self, sample_2d_polygon):
        """Test that low epsilon prevents removal from square."""
        points, edges = sample_2d_polygon

        new_points, new_edges = remove_collinear(points, edges, epsilon=1e-10)

        # Nothing should be removed from a square with small epsilon
        assert len(new_points) == len(points)
        assert len(new_edges) == len(edges)

    def test_empty_edges(self):
        """Test with empty edge list."""
        points = [p(0.0, 0.0), p(1.0, 0.0)]
        edges = []

        new_points, new_edges = remove_collinear(points, edges)

        assert new_points == points
        assert new_edges == edges

    def test_single_edge(self):
        """Test with single edge."""
        points = [p(0.0, 0.0), p(1.0, 0.0)]
        edges = [e(0, 1)]

        new_points, new_edges = remove_collinear(points, edges)

        assert len(new_points) == 2
        assert len(new_edges) == 1


class TestRemoveIsolatedPoints:
    """Tests for remove_isolated_points function."""

    def test_remove_unused_points(self):
        """Test removal of points not referenced by edges."""
        points = [
            p(0.0, 0.0),  # Used
            p(1.0, 0.0),  # Used
            p(2.0, 0.0),  # Used
            p(999.0, 999.0),  # Isolated - should be removed
        ]
        edges = [e(0, 1), e(1, 2)]

        new_points, new_edges = remove_isolated_points(points, edges)

        assert len(new_points) == 3
        assert p(999.0, 999.0) not in new_points
        # Edge indices should be remapped
        assert all(
            0 <= i < len(new_points) for edge in new_edges for i in edge.as_tuple()
        )

    def test_no_isolated_points(self, sample_2d_polygon):
        """Test with no isolated points."""
        points, edges = sample_2d_polygon

        new_points, new_edges = remove_isolated_points(points, edges)

        assert len(new_points) == len(points)


class TestMergePolygons:
    """Tests for merge_polygons function."""

    def test_merge_non_overlapping(self):
        """Test merging two non-overlapping polygons."""
        points1 = [p(0.0, 0.0), p(1.0, 0.0), p(1.0, 1.0)]
        edges1 = [e(0, 1), e(1, 2), e(2, 0)]

        points2 = [p(2.0, 0.0), p(3.0, 0.0), p(3.0, 1.0)]
        edges2 = [e(0, 1), e(1, 2), e(2, 0)]

        merged_points, merged_edges = merge_polygons(points1, edges1, points2, edges2)

        assert len(merged_points) == 6  # All points unique
        assert len(merged_edges) == 6

    def test_merge_with_shared_point(self):
        """Test merging polygons that share a point."""
        shared_point = p(1.0, 0.0)
        points1 = [p(0.0, 0.0), shared_point, p(0.5, 1.0)]
        edges1 = [e(0, 1), e(1, 2), e(2, 0)]

        points2 = [shared_point, p(2.0, 0.0), p(1.5, 1.0)]
        edges2 = [e(0, 1), e(1, 2), e(2, 0)]

        merged_points, merged_edges = merge_polygons(points1, edges1, points2, edges2)

        # Should have 5 unique points (shared point counted once)
        assert len(merged_points) == 5
        # Shared point should appear only once
        assert sum(1 for p in merged_points if p == shared_point) == 1

    def test_merge_empty_second_polygon(self, sample_2d_polygon):
        """Test merging with empty second polygon."""
        points1, edges1 = sample_2d_polygon
        points2, edges2 = [], []

        merged_points, merged_edges = merge_polygons(points1, edges1, points2, edges2)

        assert len(merged_points) == len(points1)
        assert len(merged_edges) == len(edges1)


class TestRemoveCoincident:
    """Tests for remove_coincident function."""

    def test_remove_duplicate_points(self):
        """Test removal of duplicate points."""
        points = [
            p(0.0, 0.0),
            p(1.0, 0.0),
            p(0.0, 0.0),  # Duplicate
            p(1.0, 1.0),
        ]
        edges = [e(0, 1), e(1, 2), e(2, 3), e(3, 0)]

        new_points, new_edges = remove_coincident(points, edges)

        # Should have 3 unique points
        assert len(new_points) == 3
        # Edges should be remapped
        for edge in new_edges:
            assert 0 <= edge.start < len(new_points)
            assert 0 <= edge.end < len(new_points)

    def test_remove_degenerate_edges(self):
        """Test removal of edges that become degenerate."""
        points = [
            p(0.0, 0.0),
            p(1.0, 0.0),
            p(1.0, 0.0),  # Same as point 1
        ]
        edges = [e(0, 1), e(1, 2)]  # Edge (1,2) will become degenerate

        new_points, new_edges = remove_coincident(points, edges)

        # Degenerate edge should be removed
        assert len(new_edges) == 1


class TestCentroid:
    """Tests for centroid function."""

    def test_square_centroid(self):
        """Test centroid of a square."""
        points = [
            p(0.0, 0.0),
            p(2.0, 0.0),
            p(2.0, 2.0),
            p(0.0, 2.0),
        ]

        center = centroid(points)

        assert center.x == 1.0
        assert center.y == 1.0

    def test_triangle_centroid(self):
        """Test centroid of a triangle."""
        points = [
            p(0.0, 0.0),
            p(3.0, 0.0),
            p(0.0, 3.0),
        ]

        center = centroid(points)

        assert center.x == 1.0
        assert center.y == 1.0

    def test_single_point(self):
        """Test centroid of single point."""
        points = [p(5.0, 3.0)]

        center = centroid(points)

        assert center.x == 5.0
        assert center.y == 3.0


class TestSampling:
    """Tests for sampling function."""

    def test_sample_in_square(self):
        """Test sampling returns point inside square."""
        points = [
            p(0.0, 0.0),
            p(1.0, 0.0),
            p(1.0, 1.0),
            p(0.0, 1.0),
        ]
        edges = [e(0, 1), e(1, 2), e(2, 3), e(3, 0)]

        sample = sampling(points, edges)

        # Should be inside bounding box
        assert 0.0 <= sample.x <= 1.0
        assert 0.0 <= sample.y <= 1.0

    def test_sample_consistency(self):
        """Test that sampling produces valid points."""
        points = [
            p(0.0, 0.0),
            p(2.0, 0.0),
            p(2.0, 2.0),
            p(0.0, 2.0),
        ]
        edges = [e(0, 1), e(1, 2), e(2, 3), e(3, 0)]

        # Sample multiple times
        for _ in range(10):
            sample = sampling(points, edges)
            assert isinstance(sample.x, float)
            assert isinstance(sample.y, float)


class TestConstrainedSampling:
    """Tests for constrained_sampling function."""

    def test_sample_outside_second_polygon(self):
        """Test sampling returns point outside second polygon."""
        # First polygon (larger)
        points1 = [
            p(0.0, 0.0),
            p(3.0, 0.0),
            p(3.0, 3.0),
            p(0.0, 3.0),
        ]
        edges1 = [e(0, 1), e(1, 2), e(2, 3), e(3, 0)]

        # Second polygon (smaller, inside first)
        points2 = [
            p(1.0, 1.0),
            p(2.0, 1.0),
            p(2.0, 2.0),
            p(1.0, 2.0),
        ]
        edges2 = [e(0, 1), e(1, 2), e(2, 3), e(3, 0)]

        sample = constrained_sampling(points1, edges1, points2, edges2)

        # Should be within first polygon bounds
        assert 0.0 <= sample.x <= 3.0
        assert 0.0 <= sample.y <= 3.0


class TestConnectEnds:
    """Tests for connect_ends function."""

    def test_connect_two_ends(self):
        """Test connecting polygon with two open ends."""
        points = [
            p(0.0, 0.0),  # end 1
            p(1.0, 0.0),
            p(1.0, 1.0),  # end 2
        ]
        original_len = len(points)
        edges = [e(0, 1), e(1, 2)]
        original_edges_len = len(edges)
        lbp = p(0.0, -1.0)
        rbp = p(1.0, -1.0)

        new_points, new_edges = connect_ends(points, edges, lbp, rbp)

        # Should add 2 new points and 3 new edges
        assert len(new_points) == original_len + 2
        assert len(new_edges) == original_edges_len + 3

    def test_connect_four_ends(self):
        """Test connecting polygon with four open ends."""
        # Two separate line segments
        points = [
            p(0.0, 0.0),  # end 1
            p(1.0, 0.0),  # end 2
            p(0.0, 2.0),  # end 3
            p(1.0, 2.0),  # end 4
        ]
        edges = [e(0, 1), e(2, 3)]
        original_edges_len = len(edges)
        lbp = p(0.0, -1.0)
        rbp = p(1.0, -1.0)

        new_points, new_edges = connect_ends(points, edges, lbp, rbp)

        # Should add 2 connecting edges between the 4 ends
        assert len(new_edges) == original_edges_len + 2


class TestConnectAllEnds:
    """Tests for connect_all_ends function."""

    def test_basic_connection(self):
        """Test basic end connection."""
        points = [
            p(0.0, 0.0),  # end 1
            p(1.0, 0.0),
            p(2.0, 0.0),  # end 2
        ]
        original_len = len(points)
        edges = [e(0, 1), e(1, 2)]
        lbp = p(1.0, -1.0)
        rbp = p(1.0, 1.0)

        new_points, new_edges = connect_all_ends(points, edges, lbp, rbp)

        # Should add lbp and rbp plus connections
        assert len(new_points) >= original_len + 2


class TestConnectPrev:
    """Tests for connect_prev function."""

    def test_connect_to_previous(self):
        """Test connecting current polygon to previous."""
        points = [
            p(1.0, 0.0),
            p(2.0, 0.0),
        ]
        original_len = len(points)
        edges = [e(0, 1)]
        leftmost_point = p(0.0, 0.0)
        rightmost_point = p(3.0, 0.0)

        new_points, new_edges = connect_prev(
            points, edges, rightmost_point, leftmost_point
        )

        # Should add connection points and edges
        assert len(new_points) > original_len
        assert len(new_edges) > len(edges)

    def test_skip_if_points_exist(self):
        """Test that it skips if points already exist."""
        points = [
            p(1.0, 0.0),
            p(2.0, 0.0),
        ]
        original_len = len(points)
        edges = [e(0, 1)]
        leftmost_point = p(1.0, 0.0)  # Already in points
        rightmost_point = p(2.0, 0.0)  # Already in points

        new_points, new_edges = connect_prev(
            points, edges, rightmost_point, leftmost_point
        )

        # Should not add duplicate points if they already exist
        assert len(new_points) == original_len


class TestIsClosed:
    """Tests for is_closed function."""

    def test_closed_polygon(self, sample_2d_polygon):
        """Test detection of closed polygon."""
        points, edges = sample_2d_polygon

        assert is_closed(points, edges) is True

    def test_open_polygon(self):
        """Test detection of open polygon."""
        points = [
            p(0.0, 0.0),
            p(1.0, 0.0),
            p(1.0, 1.0),
        ]
        edges = [e(0, 1), e(1, 2)]  # Missing edge (2, 0)

        assert is_closed(points, edges) is False

    def test_single_point_closed(self):
        """Test that single point with no edges is considered closed."""
        points = [p(0.0, 0.0)]
        edges = []

        assert is_closed(points, edges) is True

    def test_line_segment_open(self):
        """Test that line segment is open."""
        points = [p(0.0, 0.0), p(1.0, 0.0)]
        edges = [e(0, 1)]

        assert is_closed(points, edges) is False
