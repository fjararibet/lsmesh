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
    "gridDelta": 2.5,
    "xExtent": 110.0,
    "yExtent": 110.0,
    "trenchWidth": 70,
    "trenchHeight": 70,
    "taperAngle": 0.0,
    "processTime": 350,
    "numRaysPerPoint": 1000,
    "depositionRateP1": 0.1,
    "stickingProbabilityP1": 0.1,
    "reactionOrderP1": 1.0,
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

# process model encompasses surface model and particle types
model = ps.TEOSDeposition(
    stickingProbabilityP1=params["stickingProbabilityP1"],
    rateP1=params["depositionRateP1"],
    orderP1=params["reactionOrderP1"],
)

rayParams = ps.RayTracingParameters()
rayParams.raysPerPoint = int(params["numRaysPerPoint"])

process = ps.Process()
process.setDomain(geometry)
process.setProcessModel(model)
process.setParameters(rayParams)
process.setProcessDuration(params["processTime"])

process.apply()

lsmesh.mesh(geometry, "mesh.vtu", dimension=args.dim)


