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
else:
    print("Running 3D simulation.")
ps.setDimension(args.dim)

params = {
    "gridDelta": 0.24,
    "xExtent": 10,
    "yExtent": 10,
    "trenchWidth": 4,
    "trenchHeight": 8,
    "taperAngle": 0,
    "rate": 1.0,
    "stickingProbability": 0.1,
    "sourcePower": 1,
    "processTime": 3,
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

geometry.duplicateTopLevelSet(ps.Material.SiO2)

model = ps.SingleParticleProcess(
    stickingProbability=params["stickingProbability"],
    sourceExponent=params["sourcePower"],
)

process = ps.Process(geometry, model)
process.setProcessDuration(params["processTime"])

process.apply()

lsmesh.mesh(geometry, "mesh.vtu", dimension=args.dim)


