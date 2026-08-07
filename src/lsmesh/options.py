"""Expert mesh configuration types."""

from lsmesher.api import BuildOptions
from lsmesher.meshing import MesherOptions, MeshingOptions, MeshQuality
from lsmesher.pipeline_3d import DecimationOptions3D

MeshOptions = MeshingOptions

__all__ = [
    "BuildOptions",
    "DecimationOptions3D",
    "MeshOptions",
    "MeshQuality",
    "MesherOptions",
    "MeshingOptions",
]
