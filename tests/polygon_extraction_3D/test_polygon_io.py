"""
Regression tests for polygon_io_3d module
"""

import pytest

from lsmesher.geometry_types import Edge, Face, Point3D, Region3D

# Import from the new lsmesher package
from lsmesher.polygon_io_3d import (
    load_off,
    read_poly,
    read_vtp_edges,
    read_vtp_faces,
    read_vtp_points,
    to_off_string,
    vtp_to_poly_string,
    write_poly,
)


def p(x: float, y: float, z: float) -> Point3D:
    return Point3D(x, y, z)


def e(start: int, end: int) -> Edge:
    return Edge(start, end)


def f(*vertices: int) -> Face:
    return Face(vertices)


class TestReadPoly3D:
    """Tests for read_poly function (3D version)."""

    def test_read_simple_3d_poly(self, temp_dir):
        """Test reading a simple 3D .poly file."""
        poly_content = """4 3 0 0
1 0.0 0.0 0.0
2 1.0 0.0 0.0
3 1.0 1.0 0.0
4 0.0 1.0 0.0
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
        # Should be 3D points
        assert isinstance(points[0].x, float)
        assert isinstance(points[0].y, float)
        assert isinstance(points[0].z, float)
        assert points[0] == p(0.0, 0.0, 0.0)
        assert points[1] == p(1.0, 0.0, 0.0)

        assert len(edges) == 4


class TestWritePoly3D:
    """Tests for write_poly function (3D version)."""

    def test_write_simple_3d_poly(self, temp_dir):
        """Test writing a simple 3D .poly file."""
        points = [
            p(0.0, 0.0, 0.0),
            p(1.0, 0.0, 0.0),
            p(1.0, 1.0, 0.0),
        ]
        edges = [e(0, 1), e(1, 2), e(2, 0)]

        poly_file = temp_dir / "output.poly"
        write_poly(str(poly_file), points, edges)

        content = poly_file.read_text()
        lines = content.strip().split("\n")

        # Header should indicate 3D
        assert lines[0] == "3 3 0 0"
        # Points should have 3 coordinates
        assert lines[1] == "1 0.0 0.0 0.0"
        assert lines[2] == "2 1.0 0.0 0.0"
        assert lines[3] == "3 1.0 1.0 0.0"


class TestReadVtpPoints3D:
    """Tests for read_vtp_points function (3D version)."""

    def test_read_3d_vtp_points(self, vtp_3d_files):
        """Test reading points from 3D VTP file."""
        if not vtp_3d_files:
            pytest.skip("No 3D VTP files available")

        points = read_vtp_points(vtp_3d_files[0])

        assert len(points) > 0
        # Should be 3D points
        assert all(
            isinstance(point.x, float)
            and isinstance(point.y, float)
            and isinstance(point.z, float)
            for point in points
        )


class TestReadVtpEdges3D:
    """Tests for read_vtp_edges function (3D version)."""

    def test_read_3d_vtp_edges(self, vtp_3d_files):
        """Test reading edges from 3D VTP file."""
        if not vtp_3d_files:
            pytest.skip("No 3D VTP files available")

        edges = read_vtp_edges(vtp_3d_files[0])

        # 3D VTP files may not have edges (they have faces instead)
        # Just verify the function doesn't crash
        for edge in edges:
            assert isinstance(edge.start, int)
            assert isinstance(edge.end, int)


class TestReadVtpFaces3D:
    """Tests for read_vtp_faces function."""

    def test_read_3d_vtp_faces(self, vtp_3d_files):
        """Test reading faces from 3D VTP file."""
        if not vtp_3d_files:
            pytest.skip("No 3D VTP files available")

        faces = read_vtp_faces(vtp_3d_files[0])

        assert len(faces) > 0
        # Each face should contain vertex indices
        for face in faces:
            assert isinstance(face, Face)
            assert len(face.vertices) >= 3  # At least a triangle
            assert all(isinstance(idx, int) for idx in face.vertices)

    def test_face_indices_valid(self, vtp_3d_files):
        """Test that face indices reference valid vertices."""
        if not vtp_3d_files:
            pytest.skip("No 3D VTP files available")

        points = read_vtp_points(vtp_3d_files[0])
        faces = read_vtp_faces(vtp_3d_files[0])

        for face in faces:
            for idx in face.vertices:
                assert 0 <= idx < len(points)


class TestLoadOff:
    """Tests for load_off function."""

    def test_load_simple_off(self, temp_dir):
        """Test loading a simple OFF file."""
        off_content = """OFF
3 1 0
0.0 0.0 0.0
1.0 0.0 0.0
0.5 1.0 0.0
3 0 1 2
"""
        off_file = temp_dir / "test.off"
        off_file.write_text(off_content)

        points, faces = load_off(str(off_file))

        assert len(points) == 3
        assert points[0] == p(0.0, 0.0, 0.0)

        assert len(faces) == 1
        assert faces[0] == f(0, 1, 2)

    def test_load_off_with_comments(self, temp_dir):
        """Test loading OFF file with comments."""
        off_content = """# This is a comment
OFF
# Another comment
3 1 0
0.0 0.0 0.0
1.0 0.0 0.0
0.5 1.0 0.0
3 0 1 2
"""
        off_file = temp_dir / "test.off"
        off_file.write_text(off_content)

        points, faces = load_off(str(off_file))

        assert len(points) == 3
        assert len(faces) == 1

    def test_load_off_without_off_header(self, temp_dir):
        """Test loading OFF file without explicit OFF header fails."""
        off_content = """3 1 0
0.0 0.0 0.0
1.0 0.0 0.0
0.5 1.0 0.0
3 0 1 2
"""
        off_file = temp_dir / "test.off"
        off_file.write_text(off_content)

        # Function requires OFF header, will raise ValueError
        with pytest.raises(ValueError, match="invalid literal"):
            load_off(str(off_file))


class TestVtpToPolyString3D:
    """Tests for vtp_to_poly_string function (3D version)."""

    def test_simple_3d_mesh(self):
        """Test converting simple 3D mesh to poly string."""
        points = [
            p(0.0, 0.0, 0.0),
            p(1.0, 0.0, 0.0),
            p(0.5, 1.0, 0.0),
        ]
        faces = [f(0, 1, 2)]

        result = vtp_to_poly_string(points, faces)
        lines = result.split("\n")

        # Header should indicate 3D
        assert lines[0] == "3 3 0 0"
        # Points should have 3 coordinates
        assert lines[1] == "1 0.0 0.0 0.0"
        # Facet section
        assert "1 0 # faces" in lines[4] or lines[4] == "1 0"

    def test_3d_mesh_with_holes(self):
        """Test converting 3D mesh with holes."""
        points = [
            p(0.0, 0.0, 0.0),
            p(1.0, 0.0, 0.0),
            p(0.5, 1.0, 0.0),
        ]
        faces = [f(0, 1, 2)]
        holes = [p(0.5, 0.5, 0.0)]

        result = vtp_to_poly_string(points, faces, holes=holes)
        lines = result.split("\n")

        # Should have 1 hole
        hole_line_idx = [i for i, line in enumerate(lines) if line == "1"]
        assert len(hole_line_idx) > 0

    def test_3d_mesh_with_regions(self):
        """Test converting 3D mesh with regions."""
        points = [
            p(0.0, 0.0, 0.0),
            p(1.0, 0.0, 0.0),
            p(0.5, 1.0, 0.0),
        ]
        faces = [f(0, 1, 2)]
        regions = [Region3D(point=p(0.5, 0.5, 0.0), material=1)]

        result = vtp_to_poly_string(points, faces, regions=regions)
        lines = result.split("\n")

        # Should have 1 region
        assert "1" in lines


class TestToOffString3D:
    """Tests for to_off_string function (3D version)."""

    def test_simple_3d_to_off(self):
        """Test converting 3D points to OFF format."""
        points = [
            p(0.0, 0.0, 0.0),
            p(1.0, 0.0, 0.0),
            p(0.5, 1.0, 0.0),
        ]
        faces = [f(0, 1, 2)]

        result = to_off_string(points, faces)
        lines = result.split("\n")

        assert lines[0] == "OFF"
        assert lines[1] == "3 1 0"
        # Vertices should have 3 coordinates
        assert lines[2] == "0.0 0.0 0.0"
        assert lines[3] == "1.0 0.0 0.0"
        assert lines[4] == "0.5 1.0 0.0"
        # Face
        assert lines[5] == "3 0 1 2"

    def test_quad_face_3d(self):
        """Test OFF format with quad faces."""
        points = [
            p(0.0, 0.0, 0.0),
            p(1.0, 0.0, 0.0),
            p(1.0, 1.0, 0.0),
            p(0.0, 1.0, 0.0),
        ]
        faces = [f(0, 1, 2, 3)]

        result = to_off_string(points, faces)
        lines = result.split("\n")

        # Quad face should have 4 vertices
        assert lines[6] == "4 0 1 2 3"

    def test_multiple_faces_3d(self):
        """Test OFF format with multiple 3D faces."""
        points = [
            p(0.0, 0.0, 0.0),
            p(1.0, 0.0, 0.0),
            p(0.5, 1.0, 0.0),
            p(0.5, 0.5, 1.0),
        ]
        faces = [
            f(0, 1, 2),
            f(0, 1, 3),
            f(1, 2, 3),
        ]

        result = to_off_string(points, faces)
        lines = result.split("\n")

        assert lines[0] == "OFF"
        assert lines[1] == "4 3 0"
        # Should have 3 face lines
        assert lines[6] == "3 0 1 2"
        assert lines[7] == "3 0 1 3"
        assert lines[8] == "3 1 2 3"
