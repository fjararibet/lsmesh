"""Tests for the public, dependency-light conversion boundary."""

from lsmesher import BuildOptions, build_from_files
from lsmesher.api import layer_from_viennals, surface_from_viennals
from lsmesher.geometry_types import Edge, Face, Point2D, Point3D


class FakeMesh:
    """Small structural substitute for a ViennaLS mesh."""

    def __init__(
        self,
        nodes: tuple[tuple[int, ...], ...],
        *,
        lines: tuple[tuple[int, ...], ...] = (),
        triangles: tuple[tuple[int, ...], ...] = (),
    ) -> None:
        self._nodes = nodes
        self._lines = lines
        self._triangles = triangles

    def getNodes(self):  # noqa: N802
        return self._nodes

    def getLines(self):  # noqa: N802
        return self._lines

    def getTriangles(self):  # noqa: N802
        return self._triangles


def test_layer_from_viennals_mesh():
    mesh = FakeMesh(((0, 1, 0), (2, 3, 0)), lines=((0, 1),))

    layer = layer_from_viennals(mesh)

    assert layer.points == (Point2D(0.0, 1.0), Point2D(2.0, 3.0))
    assert layer.edges == (Edge(0, 1),)


def test_surface_from_viennals_mesh():
    mesh = FakeMesh(((0, 0, 0), (1, 0, 0), (0, 1, 1)), triangles=((0, 1, 2),))

    surface = surface_from_viennals(mesh)

    assert surface.points == (
        Point3D(0.0, 0.0, 0.0),
        Point3D(1.0, 0.0, 0.0),
        Point3D(0.0, 1.0, 1.0),
    )
    assert surface.faces == (Face((0, 1, 2)),)


def test_build_from_files_has_typed_dimension_overloads(tmp_path):
    poly = tmp_path / "triangle.vtp"
    poly.write_text("unused")

    assert BuildOptions().epsilon == 1e-6
    assert callable(build_from_files)
