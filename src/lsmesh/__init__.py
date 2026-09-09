"""Create simulation-ready meshes from ViennaLS and ViennaPS interfaces.

The package root contains everything needed for normal use. Focused submodules
such as :mod:`lsmesh.geometry`, :mod:`lsmesh.options`, and :mod:`lsmesh.errors`
remain available for browsing larger APIs.
"""

from lsmesh.api import (
    BuildOptions,
    build_3d_from_files_with_report,
    build_3d_from_viennaps_with_report,
    build_from_files,
    build_from_viennaps,
    materials_from_viennaps,
)
from lsmesh.errors import (
    AutomaticMeshingError,
    DependencyError,
    InvalidGeometryError,
    LsmeshError,
    MesherError,
    MesherNotFoundError,
    TetGenError,
    TriangleError,
    UnsupportedSourceError,
)
from lsmesh.geometry_types import Edge, Face, Point2D, Point3D, Region3D
from lsmesh.meshing import (
    MesherOptions,
    MeshingOptions,
    MeshQuality,
    mesh,
    write,
)
from lsmesh.pipeline_3d import DecimationOptions3D, DecimationReport
from lsmesh.pipeline_types import Geometry2D, Layer2D, Surface3D
from lsmesh.presets import run_preset
from lsmesh.results import (
    AutomaticMeshReport,
    MaterialInfo,
    MeshAttemptReport,
    MeshQualityReport,
    MeshResult,
    MeshResult2D,
    MeshResult3D,
    TetrahedralMesh3D,
)
from lsmesh.validation import ValidationIssue, ValidationReport, validate

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
    "LsmeshError",
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
