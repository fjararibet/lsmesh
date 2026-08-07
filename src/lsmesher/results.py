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
    minimum_shape_quality: float
    shape_quality_p05: float
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

    @property
    def acceptable(self) -> bool:
        """Whether the mesh passes the library's hard correctness checks."""
        return self.correct

    def summary(self) -> str:
        """Return a compact, human-readable quality summary."""
        status = "acceptable" if self.acceptable else "failed correctness checks"
        return (
            f"{self.element_count} elements, {status}; "
            f"shape quality p05={self.shape_quality_p05:.3g}, "
            f"worst edge ratio={self.worst_edge_ratio:.3g}"
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
    quality_target_met: bool

    @property
    def retried(self) -> bool:
        """Whether more than one meshing configuration was attempted."""
        return len(self.attempts) > 1

    @property
    def warnings(self) -> tuple[str, ...]:
        """Return failed-attempt messages and a soft quality warning."""
        messages = tuple(
            attempt.error
            for attempt in self.attempts
            if not attempt.success and attempt.error is not None
        )
        if self.quality_target_met:
            return messages
        return (*messages, f"The {self.policy} soft quality target was not met")


class _MeshResultMixin:
    """Convenience operations shared by the dimensional result types."""

    geometry: Geometry2D | Surface3D
    mesh: TriangleMesh2D | TetrahedralMesh3D | None
    materials: tuple[MaterialInfo, ...]
    output_paths: tuple[Path, ...]
    validation: ValidationReport | None
    automatic: AutomaticMeshReport | None

    @property
    def succeeded(self) -> bool:
        return self.mesh is not None

    @property
    def output_path(self) -> Path | None:
        return self.output_paths[0] if self.output_paths else None

    @property
    def report_paths(self) -> tuple[Path, ...]:
        return self.output_paths[1:]

    @property
    def material_ids(self) -> tuple[int, ...]:
        return tuple(material.material_id for material in self.materials)

    @property
    def warnings(self) -> tuple[str, ...]:
        validation_warnings = (
            tuple(
                issue.message
                for issue in self.validation.issues
                if issue.severity == "warning"
            )
            if self.validation is not None
            else ()
        )
        automatic_warnings = (
            self.automatic.warnings if self.automatic is not None else ()
        )
        return (*validation_warnings, *automatic_warnings)

    def require_mesh(self) -> TriangleMesh2D | TetrahedralMesh3D:
        """Return the generated mesh or raise when meshing was disabled."""
        if self.mesh is None:
            msg = "This result contains geometry only because meshing was disabled"
            raise RuntimeError(msg)
        return self.mesh

    def write(self, output: str | Path) -> Path:
        """Write the generated mesh, or the geometry when meshing was disabled."""
        from lsmesher.meshing import write  # noqa: PLC0415

        return write(self.mesh if self.mesh is not None else self.geometry, output)


@dataclass(frozen=True)
class MeshResult2D(_MeshResultMixin):
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
class MeshResult3D(_MeshResultMixin):
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
