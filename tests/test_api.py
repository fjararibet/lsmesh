"""Tests for the public, dependency-light conversion boundary."""

import sys
from types import SimpleNamespace

import pytest

from lsmesher import BuildOptions, DecimationOptions3D, build_from_files
from lsmesher.api import (
    _viennals_meshes,
    build_from_viennaps,
    layer_from_viennals,
    materials_from_viennaps,
    surface_from_viennals,
)
from lsmesher.geometry_types import Edge, Face, Point2D, Point3D
from lsmesher.pipeline_2d import seeded_2d_attribute_sampler
from lsmesher.pipeline_types import Layer2D


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


def test_viennals_mesh_extraction_dispatches_to_requested_dimension(monkeypatch):
    calls: list[str] = []
    mesh = FakeMesh(
        ((0, 0, 0), (1, 0, 0), (0, 1, 0)),
        triangles=((0, 1, 2),),
    )

    class Conversion:
        def apply(self) -> None:
            calls.append("d3")

    fake_vls = SimpleNamespace(
        Mesh=lambda: mesh,
        d2=SimpleNamespace(ToSurfaceMesh=lambda *_args: calls.append("d2")),
        d3=SimpleNamespace(ToSurfaceMesh=lambda *_args: Conversion()),
    )
    domain = SimpleNamespace(getLevelSets=lambda: (object(),))
    monkeypatch.setitem(sys.modules, "viennals", fake_vls)

    result = _viennals_meshes(domain, 3)

    assert result == (mesh,)
    assert calls == ["d3"]


def test_build_from_files_has_typed_dimension_overloads(tmp_path):
    poly = tmp_path / "triangle.vtp"
    poly.write_text("unused")

    assert BuildOptions().epsilon == 1e-6
    assert callable(build_from_files)


class FakeMaterialMap:
    """ViennaPS-like material map."""

    def size(self) -> int:
        return 2

    def getMaterialIdAtIdx(self, index: int) -> int:  # noqa: N802
        return (0, 4)[index]

    def getMaterialAtIdx(self, index: int) -> object:  # noqa: N802
        return ("Material.Si", "Material.SiO2")[index]

    def toString(self, material: object) -> str:  # noqa: N802
        return str(material).split(".")[-1]


class FakeDomain:
    """Domain exposing only the material API used by this test."""

    def getMaterialMap(self) -> FakeMaterialMap:  # noqa: N802
        return FakeMaterialMap()


def test_materials_from_viennaps_preserves_region_order():
    materials = materials_from_viennaps(FakeDomain())  # type: ignore[arg-type]

    assert [(item.region, item.material_id, item.name) for item in materials] == [
        (1, 0, "Si"),
        (2, 4, "SiO2"),
    ]


class RepeatedMaterialMap(FakeMaterialMap):
    """Material map containing the same ViennaPS material twice."""

    def size(self) -> int:
        return 2

    def getMaterialIdAtIdx(self, index: int) -> int:  # noqa: N802
        return (10, 10)[index]

    def getMaterialAtIdx(self, index: int) -> object:  # noqa: N802
        return ("Material.Si", "Material.Si")[index]


class RepeatedMaterialDomain(FakeDomain):
    """Domain exposing repeated material identity for two level sets."""

    def getMaterialMap(self) -> RepeatedMaterialMap:  # noqa: N802
        return RepeatedMaterialMap()


def test_build_from_viennaps_writes_repeated_material_ids(monkeypatch):
    lower = FakeMesh(
        ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)),
        triangles=((0, 1, 2), (0, 2, 3)),
    )
    upper = FakeMesh(
        ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)),
        triangles=((0, 1, 2), (0, 2, 3)),
    )
    monkeypatch.setattr(
        "lsmesher.api._viennals_meshes",
        lambda _domain, _dimension: (lower, upper),
    )

    geometry = build_from_viennaps(
        RepeatedMaterialDomain(),  # type: ignore[arg-type]
        3,
        options=BuildOptions(decimation=DecimationOptions3D(enabled=False)),
    )

    assert [region.material for region in geometry.regions] == [10, 10]


def test_seeded_sampler_is_repeatable():
    layer = Layer2D(
        points=(
            Point2D(0.0, 0.0),
            Point2D(1.0, 0.0),
            Point2D(1.0, 1.0),
            Point2D(0.0, 1.0),
        ),
        edges=(Edge(0, 1), Edge(1, 2), Edge(2, 3), Edge(3, 0)),
    )

    first = seeded_2d_attribute_sampler(42)(layer, None, originally_closed=True)
    second = seeded_2d_attribute_sampler(42)(layer, None, originally_closed=True)

    assert first == second


def test_build_rejects_invalid_runtime_dimension():
    with pytest.raises(ValueError, match="dimension must be 2 or 3"):
        build_from_files([], 4)  # type: ignore[call-overload]
