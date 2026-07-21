"""Tests for the public high-level meshing interface."""

from pathlib import Path

import pytest

from lsmesher import (
    Edge,
    Face,
    Geometry2D,
    InvalidGeometryError,
    MeshingOptions,
    Point2D,
    Point3D,
    Surface3D,
    mesh,
    validate,
    write,
)


def square_2d() -> Geometry2D:
    return Geometry2D(
        points=(
            Point2D(0.0, 0.0),
            Point2D(1.0, 0.0),
            Point2D(1.0, 1.0),
            Point2D(0.0, 1.0),
        ),
        edges=(Edge(0, 1), Edge(1, 2), Edge(2, 3), Edge(3, 0)),
    )


def triangle_3d() -> Surface3D:
    return Surface3D(
        points=(
            Point3D(0.0, 0.0, 0.0),
            Point3D(1.0, 0.0, 0.0),
            Point3D(0.0, 1.0, 0.0),
        ),
        faces=(Face((0, 1, 2)),),
    )


def test_write_selects_serializer_from_suffix(tmp_path: Path):
    output = write(square_2d(), tmp_path / "square.poly")

    assert output.read_text(encoding="utf-8").startswith("4 2 0 0")


def test_mesh_can_stop_after_geometry_construction(tmp_path: Path):
    output = tmp_path / "surface.off"

    result = mesh(
        triangle_3d(),
        output,
        dimension=3,
        options=MeshingOptions(run_mesher=False),
    )

    assert result.mesh is None
    assert result.output_paths == (output,)
    assert result.validation is not None
    assert result.validation.valid
    assert output.read_text(encoding="utf-8").startswith("OFF\n")


def test_validation_rejects_invalid_indices():
    geometry = Geometry2D(
        points=(Point2D(0.0, 0.0),),
        edges=(Edge(0, 4),),
    )

    report = validate(geometry)

    assert not report.valid
    assert report.issues[0].code == "invalid-index"
    with pytest.raises(InvalidGeometryError, match="missing points"):
        report.raise_for_errors()


def test_write_rejects_incompatible_format(tmp_path: Path):
    with pytest.raises(ValueError, match="Cannot write Geometry2D as OFF"):
        write(square_2d(), tmp_path / "square.off")
