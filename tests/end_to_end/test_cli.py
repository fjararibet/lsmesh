"""
End-to-end tests for the unified lsmesher CLI.

These tests run the full command-line pipeline from VTP inputs to OFF output
and verify the output matches expected results byte-for-byte.
"""

import subprocess
import sys
from pathlib import Path


def _pymeshlab_available():
    try:
        import pymeshlab  # noqa: F401

        return True
    except ImportError:
        return False


class Test2DExtraction:
    """End-to-end tests for 2D polygon extraction via lsmesher."""

    def test_2d_polygon_extraction_off_output(self, tmp_path):
        """
        Test full 2D pipeline: VTP files -> OFF output.

        Runs:
            lsmesher mesh --no-mesh --no-holes \
                interface_0.vtp ... interface_7.vtp \
                -o out.off

        Verifies output is a valid non-empty OFF mesh.
        """
        fixtures_dir = Path(__file__).parent / "fixtures" / "2d"
        output_file = tmp_path / "test_output.off"

        vtp_files = sorted(fixtures_dir.glob("interface_*.vtp"))
        assert len(vtp_files) == 8, f"Expected 8 VTP files, found {len(vtp_files)}"

        cmd = (
            [
                sys.executable,
                "-m",
                "lsmesher.cli",
                "mesh",
                "--no-mesh",
                "--no-holes",
            ]
            + [str(f) for f in vtp_files]
            + [
                "-o",
                str(output_file),
            ]
        )

        result = subprocess.run(cmd, capture_output=True, text=True)

        assert result.returncode == 0, (
            f"Command failed with return code {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        assert output_file.exists(), f"Output file {output_file} was not created"

        lines = output_file.read_text().splitlines()
        assert lines[0] == "OFF"
        vertex_count, face_count, edge_count = map(int, lines[1].split())
        assert vertex_count > 0
        assert face_count > 0
        assert edge_count == 0
        assert len(lines) == 2 + vertex_count + face_count


class Test3DExtraction:
    """End-to-end tests for 3D solid extraction via lsmesher."""

    def test_3d_solid_extraction_off_output(self, tmp_path):
        """
        Test full 3D pipeline: VTP file -> OFF output.

        Runs:
            lsmesher mesh --no-mesh --no-holes \
                interface_1.vtp \
                -o 3Dout.off

        Verifies output matches expected/3d_out.off byte-for-byte.
        """
        fixtures_dir = Path(__file__).parent / "fixtures" / "3d"
        expected_file = Path(__file__).parent / "expected" / "3d_out.off"
        output_file = tmp_path / "test_output.off"

        vtp_file = fixtures_dir / "interface_1.vtp"
        assert vtp_file.exists(), f"VTP file not found: {vtp_file}"

        cmd = [
            sys.executable,
            "-m",
            "lsmesher.cli",
            "mesh",
            "--no-mesh",
            "--no-holes",
            str(vtp_file),
            "-o",
            str(output_file),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        assert result.returncode == 0, (
            f"Command failed with return code {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        assert output_file.exists(), f"Output file {output_file} was not created"

        actual_output = output_file.read_bytes()
        expected_output = expected_file.read_bytes()

        assert actual_output == expected_output, (
            f"Output does not match expected byte-for-byte.\n"
            f"Output file: {output_file}\n"
            f"Expected file: {expected_file}\n"
            f"Actual size: {len(actual_output)} bytes\n"
            f"Expected size: {len(expected_output)} bytes"
        )
