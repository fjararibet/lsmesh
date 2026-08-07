"""Tests for the public high-level meshing interface."""

from pathlib import Path

import numpy as np
import pytest

import lsmesh
from lsmesher import (
    AutomaticMeshingError,
    Edge,
    Face,
    Geometry2D,
    InvalidGeometryError,
    MeshingOptions,
    MeshResult3D,
    Point2D,
    Point3D,
    Surface3D,
    mesh,
    validate,
    write,
)
from lsmesher.meshing import (
    _automatic_options,
    _decode_material_ids,
    _element_quality,
    _encode_material_ids,
    _normalize_source,
)
from lsmesher.pipeline_3d import DecimationReport
from lsmesher.results import MaterialInfo


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


def test_mesh_infers_dimension_for_typed_geometry(tmp_path: Path):
    result = mesh(
        triangle_3d(),
        tmp_path / "surface.off",
        options=MeshingOptions(run_mesher=False),
    )

    assert isinstance(result, MeshResult3D)


def test_automatic_options_scale_with_characteristic_length():
    base, safer, recovery = _automatic_options(0.25, "balanced")

    assert base.build.decimation.target_edge_length == pytest.approx(0.75)
    assert base.mesher.tetgen_max_volume == pytest.approx(1.25**3 / (6 * 2**0.5))
    assert safer.build.decimation.target_edge_length < 0.75
    assert safer.build.decimation.optimal_placement is False
    assert recovery.build.decimation.enabled is False


def test_material_encoding_is_positive_reversible_and_unifies_repeats():
    encoded, original_by_encoded = _encode_material_ids((10, 0, 0, -4))

    assert encoded == (1, 2, 3, 4)
    assert _decode_material_ids(encoded, original_by_encoded) == (10, 0, 0, -4)


def test_triangle_default_region_decodes_to_base_material():
    assert _decode_material_ids((0, 2), {1: 10, 2: 30}) == (10, 30)


def test_quality_report_detects_missing_material():
    quality = _element_quality(
        np.asarray(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ]
        ),
        np.asarray([[0, 1, 2, 3]]),
        (10,),
        (
            MaterialInfo(region=1, material_id=10, name="Si"),
            MaterialInfo(region=2, material_id=30, name="SiO2"),
        ),
    )

    assert quality.minimum_measure == pytest.approx(1 / 6)
    assert quality.minimum_shape_quality == pytest.approx(0.8399473666)
    assert quality.shape_quality_p05 == quality.minimum_shape_quality
    assert quality.missing_material_ids == (30,)
    assert not quality.correct


def test_automatic_mesh_retries_with_safer_surface_settings(tmp_path, monkeypatch):
    calls = []

    def fake_mesh_once(source, output, dimension, options):
        calls.append(options)
        if len(calls) == 1:
            message = "first PLC rejected"
            raise InvalidGeometryError(message)
        return MeshResult3D(
            geometry=source,
            mesh=None,
            output_paths=(output,),
            decimation=DecimationReport(
                mode="edge_length",
                requested_faces=10,
                original_faces=20,
                achieved_faces=10,
                protected_faces=0,
                boundary_limited_faces=0,
            ),
        )

    monkeypatch.setattr("lsmesher.meshing._mesh_once", fake_mesh_once)

    result = mesh(triangle_3d(), tmp_path / "mesh.vtu")

    assert len(calls) == 2
    assert calls[1].build.decimation.optimal_placement is False
    assert result.automatic is not None
    assert result.automatic.quality == "balanced"
    assert result.automatic.selected_attempt == "safer-surface"
    assert [attempt.success for attempt in result.automatic.attempts] == [False, True]


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


def test_mesh_rejects_quality_with_explicit_options(tmp_path: Path):
    with pytest.raises(ValueError, match="mutually exclusive"):
        mesh(
            triangle_3d(),
            tmp_path / "mesh.vtu",
            quality="fast",
            options=MeshingOptions(run_mesher=False),
        )


def test_mesh_rejects_wrong_typed_geometry_dimension(tmp_path: Path):
    with pytest.raises(ValueError, match="Geometry2D"):
        mesh(
            square_2d(),
            tmp_path / "mesh.poly",
            dimension=3,  # type: ignore[arg-type]
            options=MeshingOptions(run_mesher=False),
        )


def test_mesh_result_conveniences(tmp_path: Path):
    output = tmp_path / "surface.off"
    result = mesh(
        triangle_3d(),
        output,
        options=MeshingOptions(run_mesher=False),
    )

    assert not result.succeeded
    assert result.output_path == output
    assert result.report_paths == ()
    with pytest.raises(RuntimeError, match="meshing was disabled"):
        result.require_mesh()


def test_automatic_failure_retains_attempt_reports(tmp_path, monkeypatch):
    def fail_mesh_once(*_args: object, **_kwargs: object):
        message = "bad geometry"
        raise InvalidGeometryError(message)

    monkeypatch.setattr("lsmesher.meshing._mesh_once", fail_mesh_once)

    with pytest.raises(AutomaticMeshingError) as caught:
        mesh(triangle_3d(), tmp_path / "mesh.vtu")

    assert len(caught.value.attempts) == 3
    assert all(not attempt.success for attempt in caught.value.attempts)


def test_distribution_name_is_importable():
    assert lsmesh.mesh is mesh


def test_important_api_is_flattened():
    assert lsmesh.BuildOptions is not None
    assert lsmesh.MeshOptions is MeshingOptions
    assert lsmesh.Surface3D is Surface3D
    assert lsmesh.TetGenError is not None
    assert callable(lsmesh.build_from_files)


def test_mesh_normalizes_a_single_path(tmp_path: Path):
    interface = tmp_path / "interface.vtp"
    interface.write_text("unused", encoding="utf-8")

    assert _normalize_source(interface) == (interface,)
    assert _normalize_source(str(interface)) == (str(interface),)


def test_mesh_rejects_missing_input_path(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="does not exist"):
        mesh(tmp_path / "missing.vtp", tmp_path / "mesh.vtu", dimension=3)


def test_mesh_without_output_has_no_persistent_paths():
    result = mesh(
        triangle_3d(),
        options=MeshingOptions(run_mesher=False),
    )

    assert result.output_path is None
    assert result.output_paths == ()
    assert result.log_path is None


def test_volume_mesh_rejects_surface_output_format(tmp_path: Path):
    with pytest.raises(ValueError, match="surface-geometry format"):
        mesh(
            triangle_3d(),
            tmp_path / "mesh.vtp",
            options=MeshingOptions(),
        )
