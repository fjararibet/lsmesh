"""Public mesh error hierarchy."""

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

__all__ = [
    "AutomaticMeshingError",
    "DependencyError",
    "InvalidGeometryError",
    "LsmesherError",
    "MesherError",
    "MesherNotFoundError",
    "TetGenError",
    "TriangleError",
    "UnsupportedSourceError",
]
