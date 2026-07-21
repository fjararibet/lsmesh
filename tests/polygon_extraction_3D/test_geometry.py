"""
Regression tests for geometry_3d module
"""

import pytest

# Import from the new lsmesher package
from lsmesher.geometry_3d import (
    centroid,
    close_solid,
    connect_all_ends,
    connect_ends,
    merge_polygons_quick,
    merge_solid,
    merge_solid_quick,
    sampling,
    triangle_area,
)
from lsmesher.geometry_types import Edge, Face, Point2D, Point3D


def p(x: float, y: float, z: float) -> Point3D:
    return Point3D(x, y, z)


def p2(x: float, y: float) -> Point2D:
    return Point2D(x, y)


def e(start: int, end: int) -> Edge:
    return Edge(start, end)


def f(*vertices: int) -> Face:
    return Face(vertices)


class TestTriangleArea3D:
    """Tests for triangle_area function (3D version)."""

    def test_right_triangle_3d(self):
        """Test area of right triangle in 3D."""
        p1 = p(0.0, 0.0, 0.0)
        p2 = p(3.0, 0.0, 0.0)
        p3 = p(0.0, 4.0, 0.0)

        area = triangle_area(p1, p2, p3)

        # Area should be 0.5 * 3 * 4 = 6
        assert abs(area - 6.0) < 1e-10

    def test_triangle_in_xy_plane(self):
        """Test triangle in XY plane."""
        p1 = p(0.0, 0.0, 5.0)
        p2 = p(3.0, 0.0, 5.0)
        p3 = p(0.0, 4.0, 5.0)

        area = triangle_area(p1, p2, p3)

        # Should be same as 2D case
        assert abs(area - 6.0) < 1e-10

    def test_collinear_points_3d(self):
        """Test that collinear points give zero area in 3D."""
        p1 = p(0.0, 0.0, 0.0)
        p2 = p(1.0, 1.0, 1.0)
        p3 = p(2.0, 2.0, 2.0)

        area = triangle_area(p1, p2, p3)

        assert abs(area) < 1e-10

    def test_equilateral_triangle_3d(self):
        """Test equilateral triangle oriented in 3D space."""
        p1 = p(0.0, 0.0, 0.0)
        p2 = p(2.0, 0.0, 0.0)
        p3 = p(1.0, 1.732, 0.0)

        area = triangle_area(p1, p2, p3)

        # Should be positive
        assert area > 0


class TestMergeSolid:
    """Tests for merge_solid function."""

    def test_merge_non_overlapping_solids(self):
        """Test merging two non-overlapping solids."""
        points1 = [
            p(0.0, 0.0, 0.0),
            p(1.0, 0.0, 0.0),
            p(0.5, 1.0, 0.0),
            p(0.5, 0.5, 1.0),
        ]
        faces1 = [f(0, 1, 2), f(0, 1, 3), f(1, 2, 3), f(0, 2, 3)]

        points2 = [
            p(2.0, 0.0, 0.0),
            p(3.0, 0.0, 0.0),
            p(2.5, 1.0, 0.0),
            p(2.5, 0.5, 1.0),
        ]
        faces2 = [f(0, 1, 2), f(0, 1, 3), f(1, 2, 3), f(0, 2, 3)]

        merged_points, merged_faces = merge_solid(points1, faces1, points2, faces2)

        # Should have 8 unique points
        assert len(merged_points) == 8
        # Should have 8 faces (no duplicates)
        assert len(merged_faces) == 8

    def test_merge_with_shared_vertex(self):
        """Test merging solids that share a vertex."""
        shared = p(1.0, 0.0, 0.0)
        points1 = [p(0.0, 0.0, 0.0), shared, p(0.5, 1.0, 0.0)]
        faces1 = [f(0, 1, 2)]

        points2 = [shared, p(2.0, 0.0, 0.0), p(1.5, 1.0, 0.0)]
        faces2 = [f(0, 1, 2)]

        merged_points, merged_faces = merge_solid(points1, faces1, points2, faces2)

        # Should have 5 unique points (shared counted once)
        assert len(merged_points) == 5
        # Shared point should appear only once
        assert sum(1 for p in merged_points if p == shared) == 1

    def test_merge_duplicate_faces(self):
        """Test that duplicate faces are removed."""
        points1 = [p(0.0, 0.0, 0.0), p(1.0, 0.0, 0.0), p(0.5, 1.0, 0.0)]
        faces1 = [f(0, 1, 2)]

        points2 = [p(0.0, 0.0, 0.0), p(1.0, 0.0, 0.0), p(0.5, 1.0, 0.0)]
        faces2 = [f(0, 1, 2)]

        merged_points, merged_faces = merge_solid(points1, faces1, points2, faces2)

        # Should have only 1 face (duplicate removed)
        assert len(merged_faces) == 1


class TestMergeSolidQuick:
    """Tests for merge_solid_quick function (KDTree optimized)."""

    def test_merge_quick_basic(self):
        """Test basic merge with KDTree optimization."""
        points1 = [p(0.0, 0.0, 0.0), p(1.0, 0.0, 0.0), p(0.5, 1.0, 0.0)]
        faces1 = [f(0, 1, 2)]

        points2 = [p(2.0, 0.0, 0.0), p(3.0, 0.0, 0.0), p(2.5, 1.0, 0.0)]
        faces2 = [f(0, 1, 2)]

        merged_points, merged_faces = merge_solid_quick(
            points1, faces1, points2, faces2
        )

        # Should have 6 unique points
        assert len(merged_points) == 6
        # Should have 2 faces
        assert len(merged_faces) == 2

    def test_merge_quick_with_epsilon(self):
        """Test merge with epsilon tolerance."""
        points1 = [p(0.0, 0.0, 0.0), p(1.0, 0.0, 0.0), p(0.5, 1.0, 0.0)]
        faces1 = [f(0, 1, 2)]

        # Points very close to points1
        points2 = [p(0.0, 0.0, 0.0000001), p(1.0, 0.0, 0.0), p(0.5, 1.0, 0.0)]
        faces2 = [f(0, 1, 2)]

        merged_points, merged_faces = merge_solid_quick(
            points1, faces1, points2, faces2, epsilon=1e-5
        )

        # Should merge close points, so less than 6 total
        assert len(merged_points) < 6


class TestMergePolygonsQuick:
    """Tests for merge_polygons_quick function (KDTree optimized)."""

    def test_merge_polygons_quick_basic(self):
        """Test basic polygon merge with KDTree."""
        points1 = [p2(0.0, 0.0), p2(1.0, 0.0)]
        edges1 = [e(0, 1)]

        points2 = [p2(2.0, 0.0), p2(3.0, 0.0)]
        edges2 = [e(0, 1)]

        merged_points, merged_edges = merge_polygons_quick(
            points1,
            edges1,
            points2,
            edges2,
        )

        # Should have 4 unique points
        assert len(merged_points) == 4
        # Should have 2 edges
        assert len(merged_edges) == 2

    def test_merge_polygons_quick_with_overlap(self):
        """Test merge with overlapping points."""
        shared = p2(1.0, 0.0)
        points1 = [p2(0.0, 0.0), shared]
        edges1 = [e(0, 1)]

        points2 = [shared, p2(2.0, 0.0)]
        edges2 = [e(0, 1)]

        merged_points, merged_edges = merge_polygons_quick(
            points1,
            edges1,
            points2,
            edges2,
        )

        # Should have 3 unique points
        assert len(merged_points) == 3


class TestCentroid3D:
    """Tests for centroid function (3D version)."""

    def test_cube_centroid(self):
        """Test centroid of a cube."""
        points = [
            p(0.0, 0.0, 0.0),
            p(2.0, 0.0, 0.0),
            p(2.0, 2.0, 0.0),
            p(0.0, 2.0, 0.0),
            p(0.0, 0.0, 2.0),
            p(2.0, 0.0, 2.0),
            p(2.0, 2.0, 2.0),
            p(0.0, 2.0, 2.0),
        ]

        center = centroid(points)

        assert center.x == 1.0
        assert center.y == 1.0
        assert center.z == 1.0

    def test_tetrahedron_centroid(self):
        """Test centroid of tetrahedron."""
        points = [
            p(0.0, 0.0, 0.0),
            p(3.0, 0.0, 0.0),
            p(0.0, 3.0, 0.0),
            p(0.0, 0.0, 3.0),
        ]

        center = centroid(points)

        assert center.x == 0.75
        assert center.y == 0.75
        assert center.z == 0.75


class TestSampling3D:
    """Tests for sampling function (3D version)."""

    @pytest.mark.skip(
        reason="Infinite loop bug - will be fixed in refactor (see tests/test_bugs.py)"
    )
    def test_sample_in_cube(self):
        """Test sampling returns point inside cube."""
        points = [
            p(0.0, 0.0, 0.0),
            p(1.0, 0.0, 0.0),
            p(1.0, 1.0, 0.0),
            p(0.0, 1.0, 0.0),
            p(0.0, 0.0, 1.0),
            p(1.0, 0.0, 1.0),
            p(1.0, 1.0, 1.0),
            p(0.0, 1.0, 1.0),
        ]
        edges = [
            e(0, 1),
            e(1, 2),
            e(2, 3),
            e(3, 0),
            e(4, 5),
            e(5, 6),
            e(6, 7),
            e(7, 4),
            e(0, 4),
            e(1, 5),
            e(2, 6),
            e(3, 7),
        ]

        sample = sampling(points, edges)

        # Should be 3D point
        assert isinstance(sample.x, float)
        assert isinstance(sample.y, float)
        assert isinstance(sample.z, float)
        # Should be within bounding box
        assert 0.0 <= sample.x <= 1.0
        assert 0.0 <= sample.y <= 1.0
        assert 0.0 <= sample.z <= 1.0


class TestCloseSolid:
    """Tests for close_solid function."""

    def test_close_solid_with_border(self):
        """Test closing a solid with border points."""
        points = [
            p(0.5, 0.0, 0.0),
            p(1.0, 0.5, 0.0),
            p(0.5, 1.0, 0.0),
            p(0.0, 0.5, 0.0),
        ]
        faces = [f(0, 1, 2), f(0, 2, 3)]

        # Define 4 corner points to close the solid
        border_points = [
            p(0.0, 0.0, 0.0),
            p(1.0, 0.0, 0.0),
            p(1.0, 1.0, 0.0),
            p(0.0, 1.0, 0.0),
        ]

        new_points, new_faces = close_solid(points, faces, border_points)

        # Should add border points
        assert len(new_points) == len(points) + len(border_points)
        # Should add new faces
        assert len(new_faces) > len(faces)

    def test_close_solid_preserves_original(self):
        """Test that original points and faces are preserved."""
        points = [p(0.0, 0.0, 0.0), p(1.0, 0.0, 0.0)]
        faces = [f(0, 1)]
        border_points = [p(0.0, 1.0, 0.0), p(1.0, 1.0, 0.0)]

        new_points, new_faces = close_solid(points, faces, border_points)

        # Original points should be in result
        for point in points:
            assert point in new_points
        # Original faces should be preserved
        for face in faces:
            assert face in new_faces or any(
                set(face.vertices) == set(new_face.vertices) for new_face in new_faces
            )


class TestConnectEnds3D:
    """Tests for connect_ends function (3D version)."""

    def test_connect_two_ends_3d(self):
        """Test connecting polygon with two open ends in 3D."""
        points = [
            p(0.0, 0.0, 0.0),  # end 1
            p(1.0, 0.0, 0.0),
            p(1.0, 1.0, 0.0),  # end 2
        ]
        original_len = len(points)
        edges = [e(0, 1), e(1, 2)]
        original_edges_len = len(edges)
        lbp = p(0.0, -1.0, 0.0)
        rbp = p(1.0, -1.0, 0.0)

        new_points, new_edges = connect_ends(points, edges, lbp, rbp)

        # Should add 2 new points and 3 new edges
        assert len(new_points) == original_len + 2
        assert len(new_edges) == original_edges_len + 3


class TestConnectAllEnds3D:
    """Tests for connect_all_ends function (3D version)."""

    def test_basic_connection_3d(self):
        """Test basic end connection in 3D."""
        points = [
            p(0.0, 0.0, 0.0),  # end 1
            p(1.0, 0.0, 0.0),
            p(2.0, 0.0, 0.0),  # end 2
        ]
        original_len = len(points)
        edges = [e(0, 1), e(1, 2)]
        lbp = p(1.0, -1.0, 0.0)
        rbp = p(1.0, 1.0, 0.0)

        new_points, new_edges = connect_all_ends(points, edges, lbp, rbp)

        # Should add lbp and rbp plus connections
        assert len(new_points) >= original_len + 2

    def test_positive_negative_separation(self):
        """Test that ends are separated by positive/negative x."""
        points = [
            p(-1.0, 0.0, 0.0),  # negative x
            p(0.0, 0.0, 0.0),
            p(1.0, 0.0, 0.0),  # positive x
        ]
        edges = [e(0, 1), e(1, 2)]
        original_edges_len = len(edges)
        lbp = p(0.0, -1.0, 0.0)
        rbp = p(0.0, 1.0, 0.0)

        new_points, new_edges = connect_all_ends(points, edges, lbp, rbp)

        # Should have added connections
        assert len(new_edges) > original_edges_len
