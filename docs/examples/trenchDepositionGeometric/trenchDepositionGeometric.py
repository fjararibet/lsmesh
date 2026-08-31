from argparse import ArgumentParser
import viennaps as ps

import lsmesh

# parse config file name and simulation dimension
parser = ArgumentParser(
    prog="trenchDeposition",
    description="Run a deposition process on a trench geometry.",
)
parser.add_argument("-D", "-DIM", dest="dim", type=int, default=2)
args = parser.parse_args()

if args.dim == 2:
    print("Running 2D simulation.")
    ps.setDimension(2)
else:
    print("Running 3D simulation.")
    ps.setDimension(3)

params = {
    "gridDelta": 0.21,
    "xExtent": 10,
    "yExtent": 10,
    "trenchWidth": 4,
    "trenchHeight": 8,
    "taperAngle": 0,
    "layerThickness": 1.5,
}

geometry = ps.Domain(
    gridDelta=params["gridDelta"],
    xExtent=params["xExtent"],
    yExtent=params["yExtent"],
)
ps.MakeTrench(
    domain=geometry,
    trenchWidth=params["trenchWidth"],
    trenchDepth=params["trenchHeight"],
    trenchTaperAngle=params["taperAngle"],
).apply()


# copy top layer to capture deposition
geometry.duplicateTopLevelSet(ps.Material.SiO2)

model = ps.SphereDistribution(radius=params["layerThickness"])

ps.Process(geometry, model, 0.0).apply()

lsmesh.mesh(geometry, "mesh.vtu", dimension=args.dim)


