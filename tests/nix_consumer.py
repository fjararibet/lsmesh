"""Exercise the installed library from a consumer's Python environment."""

import importlib.util
import os
from pathlib import Path

import numpy as np
import pymeshlab
import viennals
import viennaps

import lsmesh
from lsmesh import build, errors, geometry, options

# Neither a source checkout nor executables on PATH should be needed.
assert str(Path(lsmesh.__file__).resolve()).startswith("/nix/store/")
assert importlib.util.find_spec("lsmesher") is None
assert errors.LsmeshError is lsmesh.LsmeshError
assert build.BuildOptions is lsmesh.BuildOptions
assert options.MeshOptions is lsmesh.MeshOptions
assert geometry.Surface3D is lsmesh.Surface3D
assert viennals.Mesh() is not None
assert viennaps.Domain() is not None
assert (
    pymeshlab.Mesh(
        np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
        np.array([[0, 1, 2]]),
    ).face_number()
    == 1
)
os.environ["PATH"] = ""

square = lsmesh.Geometry2D(
    points=(
        lsmesh.Point2D(0, 0),
        lsmesh.Point2D(1, 0),
        lsmesh.Point2D(1, 1),
        lsmesh.Point2D(0, 1),
    ),
    edges=(lsmesh.Edge(0, 1), lsmesh.Edge(1, 2), lsmesh.Edge(2, 3), lsmesh.Edge(3, 0)),
    attributes=(lsmesh.Point2D(0.5, 0.5),),
    attribute_ids=(1,),
)
result_2d = lsmesh.mesh(square, "square.vtu", options=lsmesh.MeshOptions())
assert result_2d.require_mesh().triangles
assert Path("square.vtu").is_file()

tetrahedron = lsmesh.Surface3D(
    points=(
        lsmesh.Point3D(0, 0, 0),
        lsmesh.Point3D(1, 0, 0),
        lsmesh.Point3D(0, 1, 0),
        lsmesh.Point3D(0, 0, 1),
    ),
    faces=(
        lsmesh.Face((0, 2, 1)),
        lsmesh.Face((0, 1, 3)),
        lsmesh.Face((1, 2, 3)),
        lsmesh.Face((2, 0, 3)),
    ),
    regions=(lsmesh.Region3D(lsmesh.Point3D(0.1, 0.1, 0.1), 1),),
)
result_3d = lsmesh.mesh(tetrahedron, "tetrahedron.vtu", options=lsmesh.MeshOptions())
assert result_3d.require_mesh().tetrahedra
assert Path("tetrahedron.vtu").is_file()
