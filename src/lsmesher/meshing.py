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
    InvalidGeometryError,
    MesherNotFoundError,
    TetGenError,
    TriangleError,
)
from lsmesher.geometry_types import Face
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
MeshPolicy: TypeAlias = Literal["fast", "balanced", "accurate"]
MeshInput: TypeAlias = ViennaPSDomain | Sequence[str | Path] | Geometry2D | Surface3D
WritableMesh: TypeAlias = Geometry2D | Surface3D | TriangleMesh2D | TetrahedralMesh3D


@dataclass(frozen=True)
class MesherOptions:
    """Quality controls passed to Triangle and TetGen."""

    triangle_min_angle: float = 20.0
    tetgen_quality_ratio: float = 2.0
    tetgen_min_dihedral: float = 0.0
    tetgen_max_volume: float | None = None
    bottom_margin: float = 0.10
    seam_protection_rings: int = 8


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
    output: str | Path,
    *,
    dimension: Literal[2] = 2,
    options: MeshingOptions | None = None,
    policy: MeshPolicy = "balanced",
) -> MeshResult2D: ...


@overload
def mesh(
    source: Surface3D,
    output: str | Path,
    *,
    dimension: Literal[3] = 3,
    options: MeshingOptions | None = None,
    policy: MeshPolicy = "balanced",
) -> MeshResult3D: ...


@overload
def mesh(
    source: ViennaPSDomain | Sequence[str | Path],
    output: str | Path,
    *,
    dimension: Literal[2],
    options: MeshingOptions | None = None,
    policy: MeshPolicy = "balanced",
) -> MeshResult2D: ...


@overload
def mesh(
    source: ViennaPSDomain | Sequence[str | Path],
    output: str | Path,
    *,
    dimension: Literal[3],
    options: MeshingOptions | None = None,
    policy: MeshPolicy = "balanced",
) -> MeshResult3D: ...


@overload
def mesh(
    source: ViennaPSDomain | Sequence[str | Path],
    output: str | Path,
    *,
    dimension: None = None,
    options: MeshingOptions | None = None,
    policy: MeshPolicy = "balanced",
) -> MeshResult2D | MeshResult3D: ...


def mesh(
    source: MeshInput,
    output: str | Path,
    *,
    dimension: Dimension | None = None,
    options: MeshingOptions | None = None,
    policy: MeshPolicy = "balanced",
) -> MeshResult2D | MeshResult3D:
    """Build, validate, mesh, and write a geometry with automatic safe defaults."""
    resolved_dimension = dimension or _infer_dimension(source)
    if options is not None:
        result = _mesh_once(source, Path(output), resolved_dimension, options)
        return _with_quality(result)
    return _mesh_automatically(
        source,
        Path(output),
        resolved_dimension,
        policy=policy,
    )


def _mesh_once(
    source: MeshInput,
    output: Path,
    dimension: Dimension,
    config: MeshingOptions,
) -> MeshResult2D | MeshResult3D:
    materials = ()
    decimation_report = None
    if isinstance(source, (Geometry2D, Surface3D)):
        geometry = source
    elif hasattr(source, "getLevelSets"):
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
    if hasattr(source, "getLevelSets"):
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
    elif hasattr(source, "getLevelSets"):
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


_POLICY_FACTORS: dict[MeshPolicy, tuple[float, float, float]] = {
    "fast": (4.0, 6.0, 2.5),
    "balanced": (3.0, 5.0, 2.0),
    "accurate": (2.0, 3.5, 1.6),
}


def _automatic_options(
    characteristic_length: float | None,
    policy: MeshPolicy,
) -> tuple[MeshingOptions, ...]:
    surface_factor, volume_factor, quality_ratio = _POLICY_FACTORS[policy]
    if characteristic_length is None:
        base = MeshingOptions(
            mesher=MesherOptions(tetgen_quality_ratio=quality_ratio)
        )
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
            None
            if base.build.decimation.target_edge_length is not None
            else 2 * 5_600
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
        mesher=replace(base.mesher, seam_protection_rings=12),
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
    policy: MeshPolicy,
) -> MeshResult2D | MeshResult3D:
    if policy not in _POLICY_FACTORS:
        msg = f"Unknown mesh policy: {policy}"
        raise ValueError(msg)
    characteristic = _characteristic_length(source, dimension)
    spacing = _grid_spacing(source)
    attempts: list[MeshAttemptReport] = []
    last_error: Exception | None = None
    names = ("scale-aware", "safer-surface", "no-decimation-recovery")
    for name, options in zip(
        names, _automatic_options(characteristic, policy), strict=True
    ):
        try:
            result = _with_quality(_mesh_once(source, output, dimension, options))
            _raise_for_quality(result.quality)
        except (InvalidGeometryError, TetGenError, TriangleError, ValueError) as error:
            attempts.append(
                _attempt_report(name, options, success=False, error=str(error))
            )
            last_error = error
            continue
        attempts.append(_attempt_report(name, options, success=True))
        automatic = AutomaticMeshReport(
            policy=policy,
            dimension=dimension,
            characteristic_length=characteristic,
            grid_spacing=spacing,
            selected_attempt=name,
            attempts=tuple(attempts),
        )
        report_path = _write_automatic_report(output, automatic, result.quality)
        return replace(
            result,
            automatic=automatic,
            output_paths=(*result.output_paths, report_path),
        )
    if last_error is not None:
        raise last_error
    msg = "Automatic meshing exhausted its attempts"
    raise InvalidGeometryError(msg)


def _quality_error(report: MeshQualityReport) -> str:
    problems: list[str] = []
    if report.element_count == 0:
        problems.append("mesher produced no elements")
    if report.minimum_measure <= 0:
        problems.append("mesh contains zero-measure elements")
    if report.missing_material_ids:
        problems.append(f"missing materials {report.missing_material_ids}")
    if report.unknown_material_ids:
        problems.append(f"unknown materials {report.unknown_material_ids}")
    return "; ".join(problems) or "mesh failed automatic correctness checks"


def _raise_for_quality(report: MeshQualityReport | None) -> None:
    if report is not None and not report.correct:
        raise InvalidGeometryError(_quality_error(report))


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
        measures = np.abs(
            np.einsum(
                "ij,ij->i",
                vertices[:, 1] - vertices[:, 0],
                np.cross(
                    vertices[:, 2] - vertices[:, 0],
                    vertices[:, 3] - vertices[:, 0],
                ),
            )
        ) / 6.0
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
    actual = set(attributes)
    expected = _expected_material_ids(materials)
    return MeshQualityReport(
        element_count=len(cells),
        minimum_measure=float(measures.min()) if measures.size else 0.0,
        minimum_edge_length=float(edge_lengths.min()) if edge_lengths.size else 0.0,
        maximum_edge_length=float(edge_lengths.max()) if edge_lengths.size else 0.0,
        worst_edge_ratio=float(ratios.max()) if ratios.size else 0.0,
        edge_ratio_p95=float(np.percentile(ratios, 95)) if ratios.size else 0.0,
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
        [
            [point.x, point.y, getattr(point, "z", 0.0)]
            for point in result.mesh.points
        ],
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
    content = {"automatic": asdict(report), "quality": asdict(quality) if quality else None}
    path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    return path


def _triangle_switches(options: MesherOptions) -> str:
    return f"-Dq{options.triangle_min_angle:g}gA"


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

    with tempfile.TemporaryDirectory(prefix="lsmesher-") as directory:
        poly_path = Path(directory) / "mesh.poly"
        write(geometry, poly_path)
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
        points, triangles, attributes = read_triangle_mesh(poly_path.with_suffix(""))
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

    executable = shutil.which("tetgen")
    if executable is None:
        mesher_name = "tetgen"
        raise MesherNotFoundError(mesher_name)
    with tempfile.TemporaryDirectory(prefix="lsmesher-") as directory:
        poly_path = Path(directory) / "mesh.poly"
        write(geometry, poly_path)
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
        points, tetrahedra, attributes = read_tetgen_mesh(poly_path.with_suffix(""))
        tetrahedral_mesh = TetrahedralMesh3D(
            tuple(points), tuple(tetrahedra), tuple(attributes)
        )
        write(tetrahedral_mesh if format_name == "vtu" else geometry, output)
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
