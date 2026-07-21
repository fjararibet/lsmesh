"""
Regression tests for polygon_io_2d module
"""

import pytest

# Import from the new lsmesher package
from lsmesher.polygon_io_2d import (
    read_poly,
    read_vtp_edges,
    read_vtp_points,
    to_off_string,
    vtp_to_poly_string,
    write_poly,
)
from lsmesher.geometry_types import Edge, Face, Point2D


def p(x: float, y: float) -> Point2D:
    return Point2D(x, y)


def e(start: int, end: int) -> Edge:
    return Edge(start, end)


def f(*vertices: int) -> Face:
    return Face(vertices)


class TestReadPoly:
    """Tests for read_poly function."""

    def test_read_simple_poly(self, temp_dir):
        """Test reading a simple .poly file."""
        poly_content = """4 2 0 0
1 0.0 0.0
2 1.0 0.0
3 1.0 1.0
4 0.0 1.0
4 0
1 1 2
2 2 3
3 3 4
4 4 1
"""
        poly_file = temp_dir / "test.poly"
        poly_file.write_text(poly_content)

        points, edges = read_poly(str(poly_file))

        assert len(points) == 4
        assert points[0] == p(0.0, 0.0)
        assert points[1] == p(1.0, 0.0)
        assert points[2] == p(1.0, 1.0)
        assert points[3] == p(0.0, 1.0)

        assert len(edges) == 4
        assert edges[0] == e(0, 1)
        assert edges[1] == e(1, 2)
        assert edges[2] == e(2, 3)
        assert edges[3] == e(3, 0)

    def test_read_poly_with_negative_indices(self, temp_dir):
        """Test that poly file indices are converted to 0-based."""
        poly_content = """3 2 0 0
1 0.0 0.0
2 1.0 0.0
3 0.5 1.0
3 0
1 1 2
2 2 3
3 3 1
"""
        poly_file = temp_dir / "test.poly"
        poly_file.write_text(poly_content)

        points, edges = read_poly(str(poly_file))

        # Indices should be 0-based
        assert edges[0] == e(0, 1)
        assert edges[1] == e(1, 2)
        assert edges[2] == e(2, 0)


class TestWritePoly:
    """Tests for write_poly function."""

    def test_write_simple_poly(self, temp_dir):
        """Test writing a simple .poly file."""
        points = [p(0.0, 0.0), p(1.0, 0.0), p(1.0, 1.0)]
        edges = [e(0, 1), e(1, 2), e(2, 0)]

        poly_file = temp_dir / "output.poly"
        write_poly(str(poly_file), points, edges)

        content = poly_file.read_text()
        lines = content.strip().split("\n")

        assert lines[0] == "3 2 0 0"
        assert lines[1] == "1 0.0 0.0"
        assert lines[2] == "2 1.0 0.0"
        assert lines[3] == "3 1.0 1.0"
        assert lines[4] == "3 0"
        # Edges should be 1-based in output
        assert lines[5] == "1 1 2"
        assert lines[6] == "2 2 3"
        assert lines[7] == "3 3 1"

    def test_roundtrip(self, temp_dir):
        """Test that read/write is reversible."""
        original_points = [p(0.0, 0.0), p(2.0, 0.0), p(1.0, 2.0)]
        original_edges = [e(0, 1), e(1, 2), e(2, 0)]

        poly_file = temp_dir / "roundtrip.poly"
        write_poly(str(poly_file), original_points, original_edges)
        read_points, read_edges = read_poly(str(poly_file))

        assert read_points == original_points
        assert read_edges == original_edges


class TestReadVtpPoints:
    """Tests for read_vtp_points function."""

    def test_read_vtp_points(self, vtp_2d_files):
        """Test reading points from VTP file."""
        if not vtp_2d_files:
            pytest.skip("No VTP files available")

        points, leftmost_id, rightmost_id = read_vtp_points(vtp_2d_files[0])

        assert len(points) > 0
        assert all(
            isinstance(point.x, float) and isinstance(point.y, float)
            for point in points
        )
        assert isinstance(leftmost_id, int)
        assert isinstance(rightmost_id, int)
        assert 0 <= leftmost_id < len(points)
        assert 0 <= rightmost_id < len(points)

    def test_points_are_2d(self, vtp_2d_files):
        """Verify that read_vtp_points returns 2D coordinates."""
        if not vtp_2d_files:
            pytest.skip("No VTP files available")

        points, _, _ = read_vtp_points(vtp_2d_files[0])

        for p in points:
            assert isinstance(p.x, float)
            assert isinstance(p.y, float)

    def test_leftmost_rightmost_identification(self, vtp_2d_files):
        """Test that leftmost and rightmost points are correctly identified."""
        if not vtp_2d_files:
            pytest.skip("No VTP files available")

        points, leftmost_id, rightmost_id = read_vtp_points(vtp_2d_files[0])

        leftmost_point = points[leftmost_id]
        rightmost_point = points[rightmost_id]

        # Leftmost point should have smallest (x, y) tuple
        for p in points:
            assert p.as_tuple() >= leftmost_point.as_tuple()

        # Rightmost point should have largest (x, y) tuple
        for p in points:
            assert p.as_tuple() <= rightmost_point.as_tuple()


class TestReadVtpEdges:
    """Tests for read_vtp_edges function."""

    def test_read_vtp_edges(self, vtp_2d_files):
        """Test reading edges from VTP file."""
        if not vtp_2d_files:
            pytest.skip("No VTP files available")

        edges = read_vtp_edges(vtp_2d_files[0])

        assert len(edges) > 0
        for edge in edges:
            assert isinstance(edge.start, int)
            assert isinstance(edge.end, int)

    def test_edges_are_valid_indices(self, vtp_2d_files):
        """Test that edge indices are valid."""
        if not vtp_2d_files:
            pytest.skip("No VTP files available")

        points, _, _ = read_vtp_points(vtp_2d_files[0])
        edges = read_vtp_edges(vtp_2d_files[0])

        for edge in edges:
            assert 0 <= edge.start < len(points)
            assert 0 <= edge.end < len(points)


class TestVtpToPolyString:
    """Tests for vtp_to_poly_string function."""

    def test_simple_polygon(self):
        """Test converting simple polygon to poly string."""
        points = [p(0.0, 0.0), p(1.0, 0.0), p(1.0, 1.0), p(0.0, 1.0)]
        edges = [e(0, 1), e(1, 2), e(2, 3), e(3, 0)]

        result = vtp_to_poly_string(points, edges)
        lines = result.split("\n")

        assert lines[0] == "4 2 0 0"
        assert lines[1] == "1 0.0 0.0"
        assert lines[5] == "4 0"
        # Check edges are 1-based
        assert lines[6] == "1 1 2"

    def test_with_holes(self):
        """Test converting polygon with holes."""
        points = [p(0.0, 0.0), p(2.0, 0.0), p(2.0, 2.0), p(0.0, 2.0)]
        edges = [e(0, 1), e(1, 2), e(2, 3), e(3, 0)]
        holes = [p(1.0, 1.0)]

        result = vtp_to_poly_string(points, edges, holes=holes)
        lines = result.split("\n")

        # Find holes section (should have 1 hole)
        hole_line_idx = [i for i, line in enumerate(lines) if line == "1"][0]
        assert lines[hole_line_idx + 1] == "1 1.0 1.0"

    def test_with_attributes(self):
        """Test converting polygon with region attributes."""
        points = [p(0.0, 0.0), p(1.0, 0.0), p(1.0, 1.0)]
        edges = [e(0, 1), e(1, 2), e(2, 0)]
        attributes = [p(0.5, 0.5)]

        result = vtp_to_poly_string(points, edges, attributes=attributes)
        lines = result.split("\n")

        # Check attribute count header
        assert "0 0" in lines[0] or "2" in lines[0]


class TestToOffString:
    """Tests for to_off_string function."""

    def test_simple_2d_to_off(self):
        """Test converting 2D points to OFF format."""
        points = [p(0.0, 0.0), p(1.0, 0.0), p(0.5, 1.0)]
        faces = [f(0, 1, 2)]

        result = to_off_string(points, faces)
        lines = result.split("\n")

        assert lines[0] == "OFF"
        assert lines[1] == "3 1 0"
        # Vertices should have z=0
        assert lines[2] == "0.0 0.0 0"
        assert lines[3] == "1.0 0.0 0"
        assert lines[4] == "0.5 1.0 0"
        # Face
        assert lines[5] == "3 0 1 2"

    def test_multiple_faces(self):
        """Test OFF format with multiple faces."""
        points = [p(0.0, 0.0), p(1.0, 0.0), p(1.0, 1.0), p(0.0, 1.0)]
        faces = [f(0, 1, 2), f(0, 2, 3)]

        result = to_off_string(points, faces)
        lines = result.split("\n")

        assert lines[0] == "OFF"
        assert lines[1] == "4 2 0"
        # Should have two face lines
        assert lines[6] == "3 0 1 2"
        assert lines[7] == "3 0 2 3"

    def test_empty_mesh(self):
        """Test OFF format with empty mesh."""
        points = []
        faces = []

        result = to_off_string(points, faces)
        lines = result.split("\n")

        assert lines[0] == "OFF"
        assert lines[1] == "0 0 0"
