"""
Test configuration and fixtures for regression tests.
"""

import os

import pytest

from lsmesher.geometry_types import Edge, Face, Point2D, Point3D


@pytest.fixture
def fixtures_dir():
    """Return the path to the fixtures directory."""
    return os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def vtp_2d_files(fixtures_dir):
    """Return list of 2D VTP test files."""
    files = []
    for i in range(8):
        filepath = os.path.join(fixtures_dir, f"interface_{i}.vtp")
        if os.path.exists(filepath):
            files.append(filepath)
    return files


@pytest.fixture
def vtp_3d_files(fixtures_dir):
    """Return list of 3D VTP test files."""
    files = []
    for i in range(1, 8):
        filepath = os.path.join(fixtures_dir, f"interface_{i}.vtp")
        if os.path.exists(filepath):
            files.append(filepath)
    return files


@pytest.fixture
def sample_2d_polygon():
    """Return a simple 2D polygon for testing."""
    points = [
        Point2D(0.0, 0.0),
        Point2D(1.0, 0.0),
        Point2D(1.0, 1.0),
        Point2D(0.0, 1.0),
    ]
    edges = [
        Edge(0, 1),
        Edge(1, 2),
        Edge(2, 3),
        Edge(3, 0),
    ]
    return points, edges


@pytest.fixture
def sample_3d_polygon():
    """Return a simple 3D polygon (tetrahedron) for testing."""
    points = [
        Point3D(0.0, 0.0, 0.0),
        Point3D(1.0, 0.0, 0.0),
        Point3D(0.5, 1.0, 0.0),
        Point3D(0.5, 0.5, 1.0),
    ]
    faces = [
        Face((0, 1, 2)),
        Face((0, 1, 3)),
        Face((1, 2, 3)),
        Face((0, 2, 3)),
    ]
    return points, faces


@pytest.fixture
def collinear_points():
    """Return points with collinear segments for testing."""
    points = [
        Point2D(0.0, 0.0),
        Point2D(0.5, 0.0),  # Collinear with 0 and 1
        Point2D(1.0, 0.0),
        Point2D(1.0, 1.0),
        Point2D(0.0, 1.0),
    ]
    edges = [
        Edge(0, 1),
        Edge(1, 2),
        Edge(2, 3),
        Edge(3, 4),
        Edge(4, 0),
    ]
    return points, edges


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for test files."""
    return tmp_path
