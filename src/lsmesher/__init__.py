"""Create simulation-ready meshes from ViennaLS and ViennaPS interfaces."""

from lsmesher.api import (
    BuildOptions,
    build_3d_from_files_with_report,
    build_3d_from_viennaps_with_report,
    build_from_files,
    build_from_viennaps,
    materials_from_viennaps,
)
from lsmesher.errors import (
    AutomaticMeshingError,
    DependencyError,
    InvalidGeometryError,
    LsmesherError,
    MesherError,
    MesherNotFoundError,
    TetGenError,
    TriangleError,
    UnsupportedSourceError,
)
from lsmesher.geometry_types import Edge, Face, Point2D, Point3D, Region3D
from lsmesher.meshing import MesherOptions, MeshingOptions, MeshQuality, mesh, write
from lsmesher.pipeline_3d import DecimationOptions3D, DecimationReport
from lsmesher.pipeline_types import Geometry2D, Layer2D, Surface3D
from lsmesher.presets import run_preset
from lsmesher.results import (
    AutomaticMeshReport,
    MaterialInfo,
    MeshAttemptReport,
    MeshQualityReport,
    MeshResult,
    MeshResult2D,
    MeshResult3D,
    TetrahedralMesh3D,
)
from lsmesher.validation import ValidationIssue, ValidationReport, validate

MeshOptions = MeshingOptions

__all__ = [
    "AutomaticMeshReport",
    "AutomaticMeshingError",
    "BuildOptions",
    "DecimationOptions3D",
    "DecimationReport",
    "DependencyError",
    "Edge",
    "Face",
    "Geometry2D",
    "InvalidGeometryError",
    "Layer2D",
    "LsmesherError",
    "MaterialInfo",
    "MeshAttemptReport",
    "MeshOptions",
    "MeshQuality",
    "MeshQualityReport",
    "MeshResult",
    "MeshResult2D",
    "MeshResult3D",
    "MesherError",
    "MesherNotFoundError",
    "MesherOptions",
    "MeshingOptions",
    "Point2D",
    "Point3D",
    "Region3D",
    "Surface3D",
    "TetGenError",
    "TetrahedralMesh3D",
    "TriangleError",
    "UnsupportedSourceError",
    "ValidationIssue",
    "ValidationReport",
    "build_3d_from_files_with_report",
    "build_3d_from_viennaps_with_report",
    "build_from_files",
    "build_from_viennaps",
    "materials_from_viennaps",
    "mesh",
    "run_preset",
    "validate",
    "write",
]
