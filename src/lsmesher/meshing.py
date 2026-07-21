"""High-level geometry serialization and external mesher orchestration."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, TypeAlias, cast, overload

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
from lsmesher.pipeline_2d import geometry_2d_to_poly_text
from lsmesher.pipeline_3d import (
    DecimationReport,
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
    MaterialInfo,
    MeshResult2D,
    MeshResult3D,
    TetrahedralMesh3D,
)
from lsmesher.validation import ValidationReport, validate

OutputFormat: TypeAlias = Literal["poly", "off", "vtp", "vtu"]
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
) -> MeshResult2D: ...


@overload
def mesh(
    source: Surface3D,
    output: str | Path,
    *,
    dimension: Literal[3] = 3,
    options: MeshingOptions | None = None,
) -> MeshResult3D: ...


@overload
def mesh(
    source: ViennaPSDomain | Sequence[str | Path],
    output: str | Path,
    *,
    dimension: Literal[2],
    options: MeshingOptions | None = None,
) -> MeshResult2D: ...


@overload
def mesh(
    source: ViennaPSDomain | Sequence[str | Path],
    output: str | Path,
    *,
    dimension: Literal[3],
    options: MeshingOptions | None = None,
) -> MeshResult3D: ...


def mesh(
    source: MeshInput,
    output: str | Path,
    *,
    dimension: Dimension,
    options: MeshingOptions | None = None,
) -> MeshResult2D | MeshResult3D:
    """Build, validate, mesh, and write a ViennaPS geometry."""
    config = options or MeshingOptions()
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
        return _mesh_2d(geometry, Path(output), config, materials, report)
    return _mesh_3d(
        geometry,
        Path(output),
        config,
        materials,
        report,
        decimation_report,
    )


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
