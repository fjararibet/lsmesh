"""High-level geometry serialization and external mesher orchestration."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Literal, TypeAlias, cast, overload

import numpy as np

from lsmesher._bin import TRIANGLE
from lsmesher.api import (
    BuildOptions,
    Dimension,
    ViennaPSDomain,
    build_3d_from_files_with_report,
    build_3d_from_viennaps_with_report,
    build_from_files,
    build_from_viennaps,
    materials_from_viennaps,
)
from lsmesher.errors import (
    AutomaticMeshingError,
    InvalidGeometryError,
    LsmesherError,
    MesherNotFoundError,
    TetGenError,
    TriangleError,
    UnsupportedSourceError,
)
from lsmesher.geometry_types import Face, Point3D, Region3D
from lsmesher.pipeline_2d import geometry_2d_to_poly_text, read_2d_layers
from lsmesher.pipeline_3d import (
    DecimationOptions3D,
    DecimationReport,
    read_3d_surfaces,
    surface_3d_to_off_text,
    surface_3d_to_poly_text,
)
from lsmesher.pipeline_types import Geometry2D, Surface3D, TriangleMesh2D
from lsmesher.polygon_io_2d import (
    read_triangle_mesh,
)
from lsmesher.polygon_io_2d import (
    to_off_string as to_off_string_2d,
)
from lsmesher.polygon_io_2d import (
    write_vtp as write_vtp_2d,
)
from lsmesher.polygon_io_2d import (
    write_vtu as write_vtu_2d,
)
from lsmesher.polygon_io_3d import (
    read_tetgen_mesh,
)
from lsmesher.polygon_io_3d import (
    write_vtp as write_vtp_3d,
)
from lsmesher.polygon_io_3d import (
    write_vtu as write_vtu_3d,
)
from lsmesher.results import (
    AutomaticMeshReport,
    MaterialInfo,
    MeshAttemptReport,
    MeshQualityReport,
    MeshResult2D,
    MeshResult3D,
    TetrahedralMesh3D,
)
from lsmesher.validation import ValidationReport, validate

OutputFormat: TypeAlias = Literal["poly", "off", "vtp", "vtu"]
MeshQuality: TypeAlias = Literal["fast", "balanced", "accurate"]
MeshInput: TypeAlias = (
    ViennaPSDomain | str | Path | Sequence[str | Path] | Geometry2D | Surface3D
)
WritableMesh: TypeAlias = Geometry2D | Surface3D | TriangleMesh2D | TetrahedralMesh3D


@dataclass(frozen=True)
class MesherOptions:
    """Quality controls passed to Triangle and TetGen."""

    triangle_min_angle: float = 20.0
    tetgen_quality_ratio: float = 2.0
    tetgen_min_dihedral: float = 0.0
    tetgen_max_volume: float | None = None


@dataclass(frozen=True)
class MeshingOptions:
    """Options for the complete build, validation, and meshing operation."""

    build: BuildOptions = field(default_factory=BuildOptions)
    mesher: MesherOptions = field(default_factory=MesherOptions)
    run_mesher: bool = True
    validate: bool = True


def output_format(path: str | Path) -> OutputFormat:
    suffix = Path(path).suffix.lower().removeprefix(".")
    if suffix not in {"poly", "off", "vtp", "vtu"}:
        msg = f"Unsupported mesh format: {Path(path).suffix or '<none>'}"
        raise ValueError(msg)
    return suffix  # type: ignore[return-value]


def write(value: WritableMesh, output: str | Path) -> Path:  # noqa: C901, PLR0912
    """Write geometry or mesher output based on the destination suffix."""
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    format_name = output_format(path)

    if isinstance(value, Geometry2D):
        if format_name == "poly":
            path.write_text(geometry_2d_to_poly_text(value), encoding="utf-8")
        elif format_name == "vtp":
            write_vtp_2d(path, value.points, tuple(_edges_as_faces(value)))
        else:
            _unsupported(value, format_name)
    elif isinstance(value, Surface3D):
        if format_name == "poly":
            path.write_text(surface_3d_to_poly_text(value), encoding="utf-8")
        elif format_name == "off":
            path.write_text(surface_3d_to_off_text(value), encoding="utf-8")
        elif format_name == "vtp":
            write_vtp_3d(path, value.points, value.faces)
        else:
            _unsupported(value, format_name)
    elif isinstance(value, TriangleMesh2D):
        if format_name == "off":
            path.write_text(
                to_off_string_2d(value.points, value.triangles), encoding="utf-8"
            )
        elif format_name == "vtp":
            write_vtp_2d(path, value.points, value.triangles)
        elif format_name == "vtu":
            write_vtu_2d(path, value.points, value.triangles, value.attributes)
        else:
            _unsupported(value, format_name)
    elif format_name == "vtu":
        write_vtu_3d(path, value.points, value.tetrahedra, value.attributes)
    else:
        _unsupported(value, format_name)
    return path


def _edges_as_faces(geometry: Geometry2D) -> Iterator[Face]:
    return (Face(edge.as_tuple()) for edge in geometry.edges)


def _unsupported(value: WritableMesh, format_name: str) -> None:
    msg = f"Cannot write {type(value).__name__} as {format_name.upper()}"
    raise ValueError(msg)


@overload
def mesh(
    source: Geometry2D,
    output: str | Path | None = None,
    *,
    dimension: Literal[2] = 2,
    options: MeshingOptions | None = None,
    quality: MeshQuality | None = None,
) -> MeshResult2D: ...


@overload
def mesh(
    source: Surface3D,
    output: str | Path | None = None,
    *,
    dimension: Literal[3] = 3,
    options: MeshingOptions | None = None,
    quality: MeshQuality | None = None,
) -> MeshResult3D: ...


@overload
def mesh(
    source: ViennaPSDomain | str | Path | Sequence[str | Path],
    output: str | Path | None = None,
    *,
    dimension: Literal[2],
    options: MeshingOptions | None = None,
    quality: MeshQuality | None = None,
) -> MeshResult2D: ...


@overload
def mesh(
    source: ViennaPSDomain | str | Path | Sequence[str | Path],
    output: str | Path | None = None,
    *,
    dimension: Literal[3],
    options: MeshingOptions | None = None,
    quality: MeshQuality | None = None,
) -> MeshResult3D: ...


@overload
def mesh(
    source: ViennaPSDomain | str | Path | Sequence[str | Path],
    output: str | Path | None = None,
    *,
    dimension: None = None,
    options: MeshingOptions | None = None,
    quality: MeshQuality | None = None,
) -> MeshResult2D | MeshResult3D: ...


def mesh(
    source: MeshInput,
    output: str | Path | None = None,
    *,
    dimension: Dimension | None = None,
    options: MeshingOptions | None = None,
    quality: MeshQuality | None = None,
) -> MeshResult2D | MeshResult3D:
    """Build and mesh a geometry using automatic safe defaults.

    Args:
        source: A ViennaPS domain, typed geometry, VTP path, or ordered sequence
            of VTP paths. A single string or :class:`~pathlib.Path` is accepted.
        output: Optional destination. ``.vtu`` writes generated elements;
            geometry formats write the intermediate boundary for compatibility.
            Prefer omitting this and calling ``result.write(...)``.
        dimension: Explicitly select 2D or 3D. It is normally inferred.
        options: Expert configuration. Supplying it selects a single attempt and
            cannot be combined with ``quality``.
        quality: Automatic goal: ``fast``, ``balanced`` (default), or ``accurate``.

    Returns:
        A dimensional result containing geometry, generated elements, quality,
        validation, materials, and automatic-attempt metadata.

    Raises:
        ValueError: If arguments conflict or dimension/quality is invalid.
        UnsupportedSourceError: If ``source`` is not a supported value.
        LsmesherError: If conversion, validation, or meshing fails.
    """
    normalized_source = _normalize_source(source)
    resolved_dimension = _resolve_dimension(normalized_source, dimension)
    if options is not None and quality is not None:
        msg = "quality and options are mutually exclusive; omit one of them"
        raise ValueError(msg)
    selected_quality = quality or "balanced"
    if output is None:
        with tempfile.TemporaryDirectory(prefix="lsmesher-result-") as directory:
            temporary_output = Path(directory) / (
                "mesh.poly"
                if options is not None
                and not options.run_mesher
                and resolved_dimension == 2
                else "mesh.off"
                if options is not None and not options.run_mesher
                else "mesh.vtu"
            )
            result = _run_mesh(
                normalized_source,
                temporary_output,
                resolved_dimension,
                options,
                selected_quality,
            )
            return replace(result, output_paths=(), log_path=None)
    return _run_mesh(
        normalized_source,
        Path(output),
        resolved_dimension,
        options,
        selected_quality,
    )


def _run_mesh(
    source: MeshInput,
    output: Path,
    dimension: Dimension,
    options: MeshingOptions | None,
    quality: MeshQuality,
) -> MeshResult2D | MeshResult3D:
    if options is not None:
        result = _mesh_once(source, output, dimension, options)
        return _with_quality(result)
    return _mesh_automatically(
        source,
        output,
        dimension,
        quality=quality,
    )


def _normalize_source(source: MeshInput) -> MeshInput:
    if isinstance(source, (Geometry2D, Surface3D)):
        return source
    if isinstance(source, (str, Path)):
        paths = (source,)
        _validate_input_paths(paths)
        return paths
    if _is_viennaps_domain(source):
        return source
    if (
        isinstance(source, Sequence)
        and not isinstance(source, (bytes, bytearray))
        and all(isinstance(item, (str, Path)) for item in source)
    ):
        paths = cast("tuple[str | Path, ...]", tuple(source))
        _validate_input_paths(paths)
        return paths
    msg = (
        "Unsupported source: expected a ViennaPS domain, Geometry2D, Surface3D, "
        "or one or more VTP paths"
    )
    raise UnsupportedSourceError(msg)


def _validate_input_paths(paths: Sequence[str | Path]) -> None:
    for value in paths:
        path = Path(value)
        if not path.exists():
            msg = f"Input interface does not exist: {path}"
            raise FileNotFoundError(msg)
        if not path.is_file():
            msg = f"Input interface is not a file: {path}"
            raise ValueError(msg)
        if path.suffix.lower() != ".vtp":
            msg = f"Input interfaces must be VTP files, got: {path}"
            raise ValueError(msg)


def _is_viennaps_domain(source: object) -> bool:
    return all(
        callable(getattr(source, method, None))
        for method in ("getLevelSets", "getMaterialMap")
    )


def _resolve_dimension(source: MeshInput, dimension: int | None) -> Dimension:
    if dimension is not None:
        if dimension not in (2, 3):
            msg = f"dimension must be 2 or 3, got {dimension!r}"
            raise ValueError(msg)
        resolved = cast("Dimension", dimension)
    else:
        resolved = _infer_dimension(source)
    if isinstance(source, Geometry2D) and resolved != 2:
        msg = "Geometry2D cannot be meshed with dimension=3"
        raise ValueError(msg)
    if isinstance(source, Surface3D) and resolved != 3:
        msg = "Surface3D cannot be meshed with dimension=2"
        raise ValueError(msg)
    return resolved


def _mesh_once(
    source: MeshInput,
    output: Path,
    dimension: Dimension,
    config: MeshingOptions,
) -> MeshResult2D | MeshResult3D:
    materials = ()
    decimation_report = None
    try:
        if isinstance(source, (Geometry2D, Surface3D)):
            geometry = source
        elif _is_viennaps_domain(source):
            domain = cast("ViennaPSDomain", source)
            if dimension == 2:
                geometry = build_from_viennaps(domain, 2, options=config.build)
            else:
                geometry, decimation_report = build_3d_from_viennaps_with_report(
                    domain, options=config.build
                )
            materials = materials_from_viennaps(domain)
        else:
            files = cast("Sequence[str | Path]", source)
            if dimension == 2:
                geometry = build_from_files(files, 2, options=config.build)
            else:
                geometry, decimation_report = build_3d_from_files_with_report(
                    files, options=config.build
                )
    except ValueError as error:
        raise InvalidGeometryError(str(error)) from error

    report = validate(geometry)
    if config.validate:
        report.raise_for_errors()
    if isinstance(geometry, Geometry2D):
        return _mesh_2d(geometry, output, config, materials, report)
    return _mesh_3d(
        geometry,
        output,
        config,
        materials,
        report,
        decimation_report,
    )


def _infer_dimension(source: MeshInput) -> Dimension:  # noqa: C901, PLR0911
    if isinstance(source, Geometry2D):
        return 2
    if isinstance(source, Surface3D):
        return 3
    if _is_viennaps_domain(source):
        module = type(source).__module__.lower()
        if ".d2" in module:
            return 2
        if ".d3" in module:
            return 3
        level_sets = source.getLevelSets()  # type: ignore[union-attr]
        if level_sets:
            level_module = type(level_sets[0]).__module__.lower()
            if ".d2" in level_module:
                return 2
            if ".d3" in level_module:
                return 3
        msg = "Cannot infer ViennaPS domain dimension; pass dimension=2 or 3"
        raise ValueError(msg)
    files = cast("Sequence[str | Path]", source)
    if not files:
        msg = "Cannot infer dimension from an empty file list"
        raise ValueError(msg)
    import vtk  # noqa: PLC0415

    reader = vtk.vtkXMLPolyDataReader()
    reader.SetFileName(str(files[0]))
    reader.Update()
    polydata = reader.GetOutput()
    has_lines = polydata.GetNumberOfLines() > 0
    has_polys = polydata.GetNumberOfPolys() > 0
    if has_lines != has_polys:
        return 2 if has_lines else 3
    msg = "Cannot infer dimension: first input must contain only lines or polygons"
    raise ValueError(msg)


def _grid_spacing(source: MeshInput) -> float | None:
    getter = getattr(source, "getGridDelta", None)
    if not callable(getter):
        return None
    spacing = float(getter())
    return spacing if math.isfinite(spacing) and spacing > 0 else None


def _geometry_edge_lengths(
    source: Geometry2D | Surface3D,
) -> np.ndarray:
    points = np.asarray([[point.x, point.y] for point in source.points], dtype=float)
    if isinstance(source, Surface3D):
        points = np.asarray(
            [[point.x, point.y, point.z] for point in source.points], dtype=float
        )
        edges = {
            tuple(sorted((start, end)))
            for face in source.faces
            for start, end in zip(
                face.vertices,
                (*face.vertices[1:], face.vertices[0]),
                strict=True,
            )
        }
    else:
        edges = {tuple(sorted(edge.as_tuple())) for edge in source.edges}
    if not edges:
        return np.asarray([], dtype=float)
    indices = np.asarray(sorted(edges), dtype=int)
    return np.linalg.norm(points[indices[:, 0]] - points[indices[:, 1]], axis=1)


def _characteristic_length(source: MeshInput, dimension: Dimension) -> float | None:
    spacing = _grid_spacing(source)
    if spacing is not None:
        return spacing
    geometry: Geometry2D | Surface3D
    if isinstance(source, (Geometry2D, Surface3D)):
        geometry = source
    elif _is_viennaps_domain(source):
        return None
    else:
        files = cast("Sequence[str | Path]", source)
        if dimension == 2:
            layer = read_2d_layers(files[:1])[0]
            geometry = Geometry2D(points=layer.points, edges=layer.edges)
        else:
            geometry = read_3d_surfaces(files[:1])[0]
    lengths = _geometry_edge_lengths(geometry)
    positive = lengths[lengths > 0]
    return float(np.median(positive)) if positive.size else None


_QUALITY_FACTORS: dict[MeshQuality, tuple[float, float, float]] = {
    "fast": (4.0, 6.0, 2.5),
    "balanced": (3.0, 5.0, 2.0),
    "accurate": (2.0, 3.5, 1.6),
}
_QUALITY_SHAPE_P05 = {"fast": 0.10, "balanced": 0.20, "accurate": 0.30}


def _automatic_options(
    characteristic_length: float | None,
    quality: MeshQuality,
) -> tuple[MeshingOptions, ...]:
    surface_factor, volume_factor, quality_ratio = _QUALITY_FACTORS[quality]
    if characteristic_length is None:
        base = MeshingOptions(mesher=MesherOptions(tetgen_quality_ratio=quality_ratio))
    else:
        surface_edge = characteristic_length * surface_factor
        volume_edge = characteristic_length * volume_factor
        max_volume = volume_edge**3 / (6.0 * math.sqrt(2.0))
        base = MeshingOptions(
            build=BuildOptions(
                decimation=DecimationOptions3D(target_edge_length=surface_edge)
            ),
            mesher=MesherOptions(
                tetgen_quality_ratio=quality_ratio,
                tetgen_max_volume=max_volume,
            ),
        )
    safer_decimation = replace(
        base.build.decimation,
        target_edge_length=(
            base.build.decimation.target_edge_length * 0.67
            if base.build.decimation.target_edge_length is not None
            else None
        ),
        target_total_faces=(
            None if base.build.decimation.target_edge_length is not None else 2 * 5_600
        ),
        optimal_placement=False,
    )
    safer = replace(
        base,
        build=replace(
            base.build,
            decimation=safer_decimation,
            seam_protection_rings=base.build.seam_protection_rings + 4,
        ),
    )
    recovery = replace(
        safer,
        build=replace(
            safer.build,
            decimation=replace(safer.build.decimation, enabled=False),
        ),
        mesher=replace(safer.mesher, tetgen_quality_ratio=2.5),
    )
    return base, safer, recovery


def _attempt_report(
    name: str,
    options: MeshingOptions,
    *,
    success: bool,
    error: str | None = None,
) -> MeshAttemptReport:
    return MeshAttemptReport(
        name=name,
        success=success,
        target_edge_length=options.build.decimation.target_edge_length,
        tetgen_max_volume=options.mesher.tetgen_max_volume,
        decimation_enabled=options.build.decimation.enabled,
        error=error,
    )


def _mesh_automatically(
    source: MeshInput,
    output: Path,
    dimension: Dimension,
    *,
    quality: MeshQuality,
) -> MeshResult2D | MeshResult3D:
    if quality not in _QUALITY_FACTORS:
        msg = f"Unknown mesh quality: {quality}"
        raise ValueError(msg)
    characteristic = _characteristic_length(source, dimension)
    spacing = _grid_spacing(source)
    attempts: list[MeshAttemptReport] = []
    last_error: Exception | None = None
    names = ("scale-aware", "safer-surface", "no-decimation-recovery")
    option_attempts = _automatic_options(characteristic, quality)
    for attempt_index, (name, options) in enumerate(
        zip(names, option_attempts, strict=True)
    ):
        try:
            result = _with_quality(_mesh_once(source, output, dimension, options))
            _raise_for_quality(result.quality)
            quality_target_met = _quality_target_met(result.quality, quality)
            _raise_for_requested_quality(
                quality,
                target_met=quality_target_met,
                final=attempt_index == len(option_attempts) - 1,
            )
        except LsmesherError as error:
            attempts.append(
                _attempt_report(name, options, success=False, error=str(error))
            )
            last_error = error
            continue
        attempts.append(_attempt_report(name, options, success=True))
        automatic = AutomaticMeshReport(
            quality=quality,
            dimension=dimension,
            characteristic_length=characteristic,
            grid_spacing=spacing,
            selected_attempt=name,
            attempts=tuple(attempts),
            quality_target_met=quality_target_met,
        )
        report_path = _write_automatic_report(output, automatic, result.quality)
        return replace(
            result,
            automatic=automatic,
            output_paths=(*result.output_paths, report_path),
        )
    if (
        dimension == 3
        and _is_viennaps_domain(source)
        and last_error is not None
        and _is_material_completeness_error(last_error)
    ):
        recovery_name = "viennaps-volume-recovery"
        recovery_options = option_attempts[-1]
        try:
            result = _with_quality(
                _mesh_native_viennaps_volume(
                    cast("ViennaPSDomain", source),
                    output,
                    recovery_options,
                )
            )
            _raise_for_quality(result.quality)
        except LsmesherError as error:
            attempts.append(
                _attempt_report(
                    recovery_name,
                    recovery_options,
                    success=False,
                    error=str(error),
                )
            )
            last_error = error
        else:
            attempts.append(
                _attempt_report(recovery_name, recovery_options, success=True)
            )
            quality_target_met = _quality_target_met(result.quality, quality)
            automatic = AutomaticMeshReport(
                quality=quality,
                dimension=dimension,
                characteristic_length=characteristic,
                grid_spacing=spacing,
                selected_attempt=recovery_name,
                attempts=tuple(attempts),
                quality_target_met=quality_target_met,
            )
            report_path = _write_automatic_report(output, automatic, result.quality)
            return replace(
                result,
                automatic=automatic,
                output_paths=(*result.output_paths, report_path),
            )
    if last_error is not None:
        raise AutomaticMeshingError(tuple(attempts), last_error) from last_error
    msg = "Automatic meshing exhausted its attempts"
    raise InvalidGeometryError(msg)


def _quality_error(report: MeshQualityReport) -> str:
    problems: list[str] = []
    if report.element_count == 0:
        problems.append("mesher produced no elements")
    if report.minimum_measure <= 0:
        problems.append("mesh contains zero-measure or inverted elements")
    if report.missing_material_ids:
        problems.append(f"missing materials {report.missing_material_ids}")
    if report.unknown_material_ids:
        problems.append(f"unknown materials {report.unknown_material_ids}")
    return "; ".join(problems) or "mesh failed automatic correctness checks"


def _is_material_completeness_error(error: Exception) -> bool:
    message = str(error)
    return "missing materials" in message or "unknown material attribute" in message


def _mesh_native_viennaps_volume(
    domain: ViennaPSDomain,
    output: Path,
    config: MeshingOptions,
) -> MeshResult3D:
    """Recover a material-complete mesh from ViennaPS's native tetrahedra.

    Wrapped level-set surfaces occasionally do not form a PLC for every
    material volume. ViennaPS can still provide its own classified volume
    representation; this is a conservative final automatic fallback after all
    smooth TetGen attempts have failed material correctness checks.
    """
    if output_format(output) != "vtu":
        msg = "ViennaPS volume recovery requires VTU output"
        raise InvalidGeometryError(msg)
    save_volume_mesh = getattr(domain, "saveVolumeMesh", None)
    if not callable(save_volume_mesh):
        msg = "ViennaPS domain does not expose native volume meshing"
        raise InvalidGeometryError(msg)

    geometry, decimation_report = build_3d_from_viennaps_with_report(
        domain, options=config.build
    )
    validation = validate(geometry)
    if config.validate:
        validation.raise_for_errors()
    materials = materials_from_viennaps(domain)

    import vtk  # noqa: PLC0415

    with tempfile.TemporaryDirectory(prefix="lsmesher-viennaps-volume-") as directory:
        prefix = Path(directory) / "mesh"
        try:
            save_volume_mesh(str(prefix))
        except RuntimeError as error:
            msg = f"ViennaPS native volume meshing failed: {error}"
            raise InvalidGeometryError(msg) from error
        volume_path = prefix.with_name(f"{prefix.name}_volume.vtu")
        if not volume_path.exists():
            msg = "ViennaPS native volume meshing produced no VTU file"
            raise InvalidGeometryError(msg)

        reader = vtk.vtkXMLUnstructuredGridReader()
        reader.SetFileName(str(volume_path))
        reader.Update()
        grid = reader.GetOutput()
        material_array = grid.GetCellData().GetArray("Material")
        if material_array is None:
            msg = "ViennaPS native volume mesh has no Material cell data"
            raise InvalidGeometryError(msg)

        points = tuple(
            Point3D(*map(float, grid.GetPoint(index)))
            for index in range(grid.GetNumberOfPoints())
        )
        tetrahedra: list[Face] = []
        attributes: list[int] = []
        for index in range(grid.GetNumberOfCells()):
            cell = grid.GetCell(index)
            if cell.GetNumberOfPoints() != 4:
                msg = "ViennaPS native volume mesh contains non-tetrahedral cells"
                raise InvalidGeometryError(msg)
            tetrahedra.append(
                Face(tuple(cell.GetPointId(vertex) for vertex in range(4)))
            )
            attributes.append(int(material_array.GetTuple1(index)))

    native_mesh = TetrahedralMesh3D(points, tuple(tetrahedra), tuple(attributes))
    write(native_mesh, output)
    return MeshResult3D(
        geometry=geometry,
        mesh=native_mesh,
        materials=materials,
        output_paths=(output,),
        validation=validation,
        decimation=decimation_report,
    )


def _raise_for_quality(report: MeshQualityReport | None) -> None:
    if report is not None and not report.correct:
        raise InvalidGeometryError(_quality_error(report))


def _quality_target_met(report: MeshQualityReport | None, quality: MeshQuality) -> bool:
    return report is None or report.shape_quality_p05 >= _QUALITY_SHAPE_P05[quality]


def _raise_for_requested_quality(
    quality: MeshQuality, *, target_met: bool, final: bool
) -> None:
    if target_met or final:
        return
    message = f"5th-percentile shape quality is below the {quality} target"
    raise InvalidGeometryError(message)


def _expected_material_ids(materials: tuple[MaterialInfo, ...]) -> set[int]:
    return {material.material_id for material in materials}


def _element_quality(
    points: np.ndarray,
    cells: np.ndarray,
    attributes: tuple[int, ...],
    materials: tuple[MaterialInfo, ...],
) -> MeshQualityReport:
    vertices = points[cells]
    if cells.shape[1] == 3:
        doubled_area = np.linalg.norm(
            np.cross(vertices[:, 1] - vertices[:, 0], vertices[:, 2] - vertices[:, 0]),
            axis=1,
        )
        measures = doubled_area / 2.0
        edge_pairs = ((0, 1), (1, 2), (2, 0))
    else:
        measures = (
            np.einsum(
                "ij,ij->i",
                vertices[:, 1] - vertices[:, 0],
                np.cross(
                    vertices[:, 2] - vertices[:, 0],
                    vertices[:, 3] - vertices[:, 0],
                ),
            )
            / 6.0
        )
        edge_pairs = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
    edge_lengths = np.stack(
        [
            np.linalg.norm(vertices[:, first] - vertices[:, second], axis=1)
            for first, second in edge_pairs
        ],
        axis=1,
    )
    minimum_edges = edge_lengths.min(axis=1)
    ratios = np.divide(
        edge_lengths.max(axis=1),
        minimum_edges,
        out=np.full_like(minimum_edges, np.inf),
        where=minimum_edges > 0,
    )
    squared_edge_sum = np.sum(edge_lengths**2, axis=1)
    if cells.shape[1] == 3:
        shape_quality = np.divide(
            4.0 * math.sqrt(3.0) * measures,
            squared_edge_sum,
            out=np.zeros_like(measures),
            where=squared_edge_sum > 0,
        )
    else:
        positive_measure = np.maximum(measures, 0.0)
        shape_quality = np.divide(
            12.0 * np.power(3.0 * positive_measure, 2.0 / 3.0),
            squared_edge_sum,
            out=np.zeros_like(measures),
            where=squared_edge_sum > 0,
        )
    actual = set(attributes)
    expected = _expected_material_ids(materials)
    return MeshQualityReport(
        element_count=len(cells),
        minimum_measure=float(measures.min()) if measures.size else 0.0,
        minimum_edge_length=float(edge_lengths.min()) if edge_lengths.size else 0.0,
        maximum_edge_length=float(edge_lengths.max()) if edge_lengths.size else 0.0,
        worst_edge_ratio=float(ratios.max()) if ratios.size else 0.0,
        edge_ratio_p95=float(np.percentile(ratios, 95)) if ratios.size else 0.0,
        minimum_shape_quality=(
            float(shape_quality.min()) if shape_quality.size else 0.0
        ),
        shape_quality_p05=(
            float(np.percentile(shape_quality, 5)) if shape_quality.size else 0.0
        ),
        material_ids=tuple(sorted(actual)),
        missing_material_ids=tuple(sorted(expected - actual)),
        unknown_material_ids=tuple(sorted(actual - expected)) if expected else (),
    )


def _with_quality(
    result: MeshResult2D | MeshResult3D,
) -> MeshResult2D | MeshResult3D:
    if result.mesh is None:
        return result
    points = np.asarray(
        [[point.x, point.y, getattr(point, "z", 0.0)] for point in result.mesh.points],
        dtype=float,
    )
    cells_source = (
        result.mesh.triangles
        if isinstance(result, MeshResult2D)
        else result.mesh.tetrahedra
    )
    cells = np.asarray([cell.vertices for cell in cells_source], dtype=int)
    quality = _element_quality(points, cells, result.mesh.attributes, result.materials)
    return replace(result, quality=quality)


def _write_automatic_report(
    output: Path,
    report: AutomaticMeshReport,
    quality: MeshQualityReport | None,
) -> Path:
    path = output.with_name(f"{output.stem}.automatic.json")
    content = {
        "automatic": asdict(report),
        "quality": asdict(quality) if quality else None,
    }
    path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    return path


def _triangle_switches(options: MesherOptions) -> str:
    # ``-p`` tells Triangle to mesh the segments, holes, and regions from the
    # .poly file.  Without it Triangle meshes only the point set's convex hull,
    # leaving cells with attribute 0 and ignoring material interfaces.
    return f"-pDq{options.triangle_min_angle:g}gA"


def _tetgen_switches(options: MesherOptions) -> str:
    quality = f"q{options.tetgen_quality_ratio:g}"
    if options.tetgen_min_dihedral > 0:
        quality += f"/{options.tetgen_min_dihedral:g}"
    volume = (
        f"a{options.tetgen_max_volume:g}"
        if options.tetgen_max_volume is not None
        else ""
    )
    return f"-p{quality}AkR{volume}"


def _encode_material_ids(
    material_ids: Sequence[int],
) -> tuple[tuple[int, ...], dict[int, int]]:
    """Replace application IDs with positive, consecutive mesher attributes."""
    original_by_encoded = {
        index + 1: material_id for index, material_id in enumerate(material_ids)
    }
    return tuple(original_by_encoded), original_by_encoded


def _decode_material_ids(
    material_ids: Sequence[int], original_by_encoded: dict[int, int]
) -> tuple[int, ...]:
    # Triangle reserves zero for the default region containing the base level
    # set. ViennaPS orders that base material first.
    base_material = original_by_encoded.get(1)
    try:
        return tuple(
            base_material
            if material_id == 0 and base_material is not None
            else original_by_encoded[material_id]
            for material_id in material_ids
        )
    except KeyError as error:
        msg = f"Mesher returned unknown material attribute {error.args[0]}"
        raise InvalidGeometryError(msg) from error


def _mesh_2d(
    geometry: Geometry2D,
    output: Path,
    config: MeshingOptions,
    materials: tuple[MaterialInfo, ...],
    report: ValidationReport,
) -> MeshResult2D:
    format_name = output_format(output)
    if not config.run_mesher:
        try:
            write(geometry, output)
        except ValueError as error:
            msg = f"{format_name.upper()} output requires Triangle; remove --no-mesh"
            raise InvalidGeometryError(msg) from error
        return MeshResult2D(geometry, None, materials, (output,), validation=report)

    if format_name == "poly":
        msg = (
            "POLY is a boundary-geometry format, not a generated mesh format; "
            "use run_mesher=False or write(result.geometry, output)"
        )
        raise ValueError(msg)

    with tempfile.TemporaryDirectory(prefix="lsmesher-") as directory:
        poly_path = Path(directory) / "mesh.poly"
        original_ids = geometry.attribute_ids or tuple(
            range(1, len(geometry.attributes) + 1)
        )
        encoded_ids, original_by_encoded = _encode_material_ids(original_ids)
        mesher_geometry = replace(geometry, attribute_ids=encoded_ids)
        write(mesher_geometry, poly_path)
        command = (str(TRIANGLE), _triangle_switches(config.mesher), str(poly_path))
        if not TRIANGLE.exists():
            mesher_name = "triangle"
            raise MesherNotFoundError(mesher_name)
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        log_path = output.with_name(f"{output.stem}.triangle.log")
        _write_log(log_path, command, completed)
        if completed.returncode:
            mesher_name = "Triangle"
            raise TriangleError(
                mesher_name,
                command,
                completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                log_path=log_path,
            )
        points, triangles, encoded_attributes = read_triangle_mesh(
            poly_path.with_suffix("")
        )
        attributes = _decode_material_ids(encoded_attributes, original_by_encoded)
        triangle_mesh = TriangleMesh2D(
            tuple(points), tuple(triangles), tuple(attributes)
        )
        write(geometry if format_name == "poly" else triangle_mesh, output)
    return MeshResult2D(geometry, triangle_mesh, materials, (output,), log_path, report)


def _mesh_3d(  # noqa: PLR0913
    geometry: Surface3D,
    output: Path,
    config: MeshingOptions,
    materials: tuple[MaterialInfo, ...],
    report: ValidationReport,
    decimation_report: DecimationReport | None,
) -> MeshResult3D:
    format_name = output_format(output)
    report_path = _write_decimation_report(output, decimation_report)
    output_paths = (output,) if report_path is None else (output, report_path)
    if not config.run_mesher:
        try:
            write(geometry, output)
        except ValueError as error:
            msg = f"{format_name.upper()} output requires TetGen; remove --no-mesh"
            raise InvalidGeometryError(msg) from error
        return MeshResult3D(
            geometry,
            None,
            materials,
            output_paths,
            validation=report,
            decimation=decimation_report,
        )

    if format_name != "vtu":
        msg = (
            f"{format_name.upper()} is a surface-geometry format, not a volume "
            "mesh format; use a .vtu output or write(result.geometry, output)"
        )
        raise ValueError(msg)

    executable = shutil.which("tetgen")
    if executable is None:
        mesher_name = "tetgen"
        raise MesherNotFoundError(mesher_name)
    with tempfile.TemporaryDirectory(prefix="lsmesher-") as directory:
        poly_path = Path(directory) / "mesh.poly"
        encoded_ids, original_by_encoded = _encode_material_ids(
            tuple(region.material for region in geometry.regions)
        )
        mesher_geometry = replace(
            geometry,
            regions=tuple(
                Region3D(region.point, material_id)
                for region, material_id in zip(
                    geometry.regions, encoded_ids, strict=True
                )
            ),
        )
        write(mesher_geometry, poly_path)
        command = (executable, _tetgen_switches(config.mesher), str(poly_path))
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        log_path = output.with_name(f"{output.stem}.tetgen.log")
        _write_log(log_path, command, completed)
        if completed.returncode:
            mesher_name = "TetGen"
            raise TetGenError(
                mesher_name,
                command,
                completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                log_path=log_path,
            )
        points, tetrahedra, encoded_attributes = read_tetgen_mesh(
            poly_path.with_suffix("")
        )
        attributes = _decode_material_ids(encoded_attributes, original_by_encoded)
        tetrahedral_mesh = TetrahedralMesh3D(
            tuple(points), tuple(tetrahedra), tuple(attributes)
        )
        write(tetrahedral_mesh, output)
    return MeshResult3D(
        geometry,
        tetrahedral_mesh,
        materials,
        output_paths,
        log_path,
        report,
        decimation_report,
    )


def _write_decimation_report(
    output: Path, report: DecimationReport | None
) -> Path | None:
    if report is None:
        return None
    path = output.with_name(f"{output.stem}.decimation.json")
    path.write_text(json.dumps(asdict(report), indent=2) + "\n", encoding="utf-8")
    return path


def _write_log(
    path: Path,
    command: tuple[str, ...],
    completed: subprocess.CompletedProcess[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n\n".join(
        part
        for part in (
            f"Command: {' '.join(command)}",
            completed.stdout,
            completed.stderr,
        )
        if part
    )
    path.write_text(text, encoding="utf-8")
