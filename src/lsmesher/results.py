"""Typed values returned by high-level meshing operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from pathlib import Path

    from lsmesher.geometry_types import Face, Point3D
    from lsmesher.pipeline_3d import DecimationReport
    from lsmesher.pipeline_types import Geometry2D, Surface3D, TriangleMesh2D
    from lsmesher.validation import ValidationReport


@dataclass(frozen=True)
class MaterialInfo:
    """ViennaPS material assigned to one mesh region."""

    region: int
    material_id: int
    name: str


@dataclass(frozen=True)
class TetrahedralMesh3D:
    """TetGen output with one material attribute per tetrahedron."""

    points: tuple[Point3D, ...]
    tetrahedra: tuple[Face, ...]
    attributes: tuple[int, ...]


@dataclass(frozen=True)
class MeshResult2D:
    """Geometry, optional Triangle mesh, metadata, and generated files."""

    geometry: Geometry2D
    mesh: TriangleMesh2D | None
    materials: tuple[MaterialInfo, ...] = ()
    output_paths: tuple[Path, ...] = ()
    log_path: Path | None = None
    validation: ValidationReport | None = None


@dataclass(frozen=True)
class MeshResult3D:
    """Geometry, optional TetGen mesh, metadata, and generated files."""

    geometry: Surface3D
    mesh: TetrahedralMesh3D | None
    materials: tuple[MaterialInfo, ...] = ()
    output_paths: tuple[Path, ...] = ()
    log_path: Path | None = None
    validation: ValidationReport | None = None
    decimation: DecimationReport | None = None


MeshResult: TypeAlias = MeshResult2D | MeshResult3D
