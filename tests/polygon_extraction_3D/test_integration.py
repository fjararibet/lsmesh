"""
Integration tests for 3D solid extraction workflow.
Tests the full workflow from VTP files to 3D POLY output.
"""

import pytest

from lsmesher import geometry_3d as geometry

# Import from the new lsmesher package
from lsmesher.polygon_io_3d import (
    read_vtp_faces,
    read_vtp_points,
    to_off_string,
    vtp_to_poly_string,
)
from lsmesher.geometry_types import Face, Point3D, Region3D


class TestMainWorkflow3D:
    """Integration tests for the 3D workflow."""

    def test_single_vtp_file_processing_3d(self, vtp_3d_files, temp_dir):
        """Test processing a single 3D VTP file through the full workflow."""
        if not vtp_3d_files:
            pytest.skip("No 3D VTP files available")

        vtp_file = vtp_3d_files[0]

        # Read the VTP file
        points = read_vtp_points(vtp_file)
        faces = read_vtp_faces(vtp_file)

        assert len(points) > 0
        assert len(faces) > 0

        # Verify all face indices are valid
        for face in faces:
            for idx in face.vertices:
                assert 0 <= idx < len(points)

        # Generate poly string (TetGen format)
        poly_string = vtp_to_poly_string(
            points=points,
            faces=faces,
        )

        # Verify output
        assert len(poly_string) > 0
        assert str(len(points)) in poly_string
        assert str(len(faces)) in poly_string
        # Should indicate 3D
        assert "3" in poly_string.split("\n")[0]

    def test_off_output_format_3d(self, vtp_3d_files, temp_dir):
        """Test generating OFF format output from 3D mesh."""
        if not vtp_3d_files:
            pytest.skip("No 3D VTP files available")

        points = read_vtp_points(vtp_3d_files[0])
        faces = read_vtp_faces(vtp_3d_files[0])

        off_string = to_off_string(points, faces)

        lines = off_string.split("\n")
        assert lines[0] == "OFF"
        # Header line should have counts
        header_parts = lines[1].split()
        assert len(header_parts) == 3
        assert int(header_parts[0]) == len(points)
        assert int(header_parts[1]) == len(faces)

    def test_multiple_vtp_files_processing(self, vtp_3d_files, temp_dir):
        """Test processing multiple 3D VTP files."""
        if len(vtp_3d_files) < 2:
            pytest.skip("Need at least 2 VTP files")

        all_points: list[Point3D] = []
        all_faces: list[Face] = []

        for vtp_file in vtp_3d_files[:2]:  # Test with first 2 files
            points = read_vtp_points(vtp_file)
            faces = read_vtp_faces(vtp_file)

            # Simulate merging (simple append for this test)
            offset = len(all_points)
            all_points.extend(points)
            all_faces.extend(
                Face(tuple(idx + offset for idx in face.vertices)) for face in faces
            )

        # Verify combined mesh
        assert len(all_points) > 0
        assert len(all_faces) > 0

        # All face indices should be valid
        for face in all_faces:
            for idx in face.vertices:
                assert 0 <= idx < len(all_points)

    def test_poly_output_with_regions(self, vtp_3d_files, temp_dir):
        """Test generating POLY output with regions."""
        if not vtp_3d_files:
            pytest.skip("No 3D VTP files available")

        points = read_vtp_points(vtp_3d_files[0])
        faces = read_vtp_faces(vtp_3d_files[0])

        # Calculate centroid as region point
        center = geometry.centroid(points)
        regions = [Region3D(point=center, material=1)]

        poly_string = vtp_to_poly_string(
            points=points,
            faces=faces,
            regions=regions,
        )

        # Should contain region information
        lines = poly_string.split("\n")
        assert any("1" in line for line in lines)  # At least 1 region

    def test_full_pipeline_output(self, vtp_3d_files, temp_dir):
        """Test the complete pipeline from VTP to output file."""
        if not vtp_3d_files:
            pytest.skip("No 3D VTP files available")

        vtp_file = vtp_3d_files[0]
        output_file = temp_dir / "output.poly"

        # Read VTP
        points = read_vtp_points(vtp_file)
        faces = read_vtp_faces(vtp_file)

        # Convert to POLY string
        poly_string = vtp_to_poly_string(points, faces)

        # Write to file
        output_file.write_text(poly_string)

        # Verify file was created and has content
        assert output_file.exists()
        content = output_file.read_text()
        assert len(content) > 0
        assert str(len(points)) in content


class TestMeshDecimationWorkflow:
    """Tests for mesh decimation workflow (pymeshlab integration)."""

    def test_mesh_loading(self, vtp_3d_files):
        """Test that VTP files can be loaded as meshes."""
        if not vtp_3d_files:
            pytest.skip("No 3D VTP files available")

        try:
            import numpy as np
            import pymeshlab as ml

            points = read_vtp_points(vtp_3d_files[0])
            faces = read_vtp_faces(vtp_3d_files[0])

            # Convert to numpy arrays
            points_array = np.array([point.as_tuple() for point in points])
            faces_array = np.array([face.as_tuple() for face in faces])

            # Create mesh
            mesh = ml.Mesh(vertex_matrix=points_array, face_matrix=faces_array)  # type: ignore[attr-defined]

            assert mesh is not None
            assert mesh.vertex_number() == len(points)
            assert mesh.face_number() == len(faces)

        except ImportError:
            pytest.skip("pymeshlab not available")

    def test_mesh_decimation(self, vtp_3d_files):
        """Test mesh decimation reduces face count."""
        if not vtp_3d_files:
            pytest.skip("No 3D VTP files available")

        try:
            import numpy as np
            import pymeshlab as ml

            points = read_vtp_points(vtp_3d_files[0])
            faces = read_vtp_faces(vtp_3d_files[0])

            points_array = np.array([point.as_tuple() for point in points])
            faces_array = np.array([face.as_tuple() for face in faces])

            mesh = ml.Mesh(vertex_matrix=points_array, face_matrix=faces_array)  # type: ignore[attr-defined]
            ms = ml.MeshSet()  # type: ignore[attr-defined]
            ms.add_mesh(mesh, "original")

            original_faces = ms.current_mesh().face_number()

            # Decimate
            ms.meshing_decimation_quadric_edge_collapse(
                targetfacenum=100,
                qualitythr=0.3,
            )

            decimated_faces = ms.current_mesh().face_number()

            # Should have reduced or maintained face count
            assert decimated_faces <= original_faces

        except ImportError:
            pytest.skip("pymeshlab not available")


class TestTetGenOutput:
    """Tests for TetGen output generation."""

    def test_tetgen_poly_format(self, vtp_3d_files, temp_dir):
        """Test that output is in valid TetGen POLY format."""
        if not vtp_3d_files:
            pytest.skip("No 3D VTP files available")

        points = read_vtp_points(vtp_3d_files[0])
        faces = read_vtp_faces(vtp_3d_files[0])

        poly_string = vtp_to_poly_string(points, faces)
        lines = poly_string.split("\n")

        # Check structure
        # Line 0: Node list header
        node_header = lines[0].split()
        assert len(node_header) >= 2
        assert int(node_header[0]) == len(points)
        assert int(node_header[1]) == 3  # 3D

        # Find facet section
        facet_line_idx = None
        for i, line in enumerate(lines):
            if "# faces" in line or (
                line.strip() and line.split()[0].isdigit() and i > len(points)
            ):
                facet_line_idx = i
                break

        assert facet_line_idx is not None
        facet_header = lines[facet_line_idx].split()
        assert int(facet_header[0]) == len(faces)

    def test_tetgen_with_holes(self, vtp_3d_files, temp_dir):
        """Test TetGen output with holes."""
        if not vtp_3d_files:
            pytest.skip("No 3D VTP files available")

        points = read_vtp_points(vtp_3d_files[0])
        faces = read_vtp_faces(vtp_3d_files[0])

        # Add a hole
        center = geometry.centroid(points)
        holes = [center]

        poly_string = vtp_to_poly_string(points, faces, holes=holes)
        lines = poly_string.split("\n")

        # Should have hole section
        assert any(line.strip() == "1" for line in lines)
