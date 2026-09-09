"""Expert mesh configuration types."""

from lsmesh.api import BuildOptions
from lsmesh.meshing import MesherOptions, MeshingOptions, MeshQuality
from lsmesh.pipeline_3d import DecimationOptions3D

MeshOptions = MeshingOptions

__all__ = [
    "BuildOptions",
    "DecimationOptions3D",
    "MeshOptions",
    "MeshQuality",
    "MesherOptions",
    "MeshingOptions",
]
