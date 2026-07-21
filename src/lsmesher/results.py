"""Typed values returned by high-level meshing operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypeAlias

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
class MeshQualityReport:
    """Measured element and material properties of a generated mesh."""

    element_count: int
    minimum_measure: float
    minimum_edge_length: float
    maximum_edge_length: float
    worst_edge_ratio: float
    edge_ratio_p95: float
    material_ids: tuple[int, ...]
    missing_material_ids: tuple[int, ...] = ()
    unknown_material_ids: tuple[int, ...] = ()

    @property
    def correct(self) -> bool:
        return (
            self.element_count > 0
            and self.minimum_measure > 0
            and not self.missing_material_ids
            and not self.unknown_material_ids
        )


@dataclass(frozen=True)
class MeshAttemptReport:
    """One configuration tried by automatic meshing."""

    name: str
    success: bool
    target_edge_length: float | None
    tetgen_max_volume: float | None
    decimation_enabled: bool
    error: str | None = None


@dataclass(frozen=True)
class AutomaticMeshReport:
    """Decisions and recovery attempts made by automatic meshing."""

    policy: Literal["fast", "balanced", "accurate"]
    dimension: Literal[2, 3]
    characteristic_length: float | None
    grid_spacing: float | None
    selected_attempt: str
    attempts: tuple[MeshAttemptReport, ...]


@dataclass(frozen=True)
class MeshResult2D:
    """Geometry, optional Triangle mesh, metadata, and generated files."""

    geometry: Geometry2D
    mesh: TriangleMesh2D | None
    materials: tuple[MaterialInfo, ...] = ()
    output_paths: tuple[Path, ...] = ()
    log_path: Path | None = None
    validation: ValidationReport | None = None
    quality: MeshQualityReport | None = None
    automatic: AutomaticMeshReport | None = None


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
    quality: MeshQualityReport | None = None
    automatic: AutomaticMeshReport | None = None


MeshResult: TypeAlias = MeshResult2D | MeshResult3D
