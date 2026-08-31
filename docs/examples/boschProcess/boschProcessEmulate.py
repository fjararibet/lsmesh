from argparse import ArgumentParser
import viennaps as ps

import lsmesh


# parse config file name and simulation dimension
parser = ArgumentParser(
    prog="boschProcessEmulate",
    description="Run a Bosch process emulation on a trench geometry.",
)
parser.add_argument("-D", "-DIM", dest="dim", type=int, default=2)
args = parser.parse_args()

# switch between 2D and 3D mode
if args.dim == 2:
    print("Running 2D simulation.")
else:
    print("Running 3D simulation.")
ps.setDimension(args.dim)

ps.Logger.setLogLevel(ps.LogLevel.ERROR)
params = {
    "gridDelta": 0.1,
    "xExtent": 3.5,
    "yExtent": 1.5,
    "trenchWidth": 2.0,
    "maskHeight": 0.6,
    "depositionStickingProbability": 0.01,
    "depositionThickness": 0.075,
    "neutralStickingProbability": 0.1,
    "neutralRate": -0.2,
    "ionSourceExponent": 200,
    "ionRate": -0.1,
    "etchTime": 0.5,
    "numCycles": 1,
}
ps.setNumThreads(16)

geometry = ps.Domain(
    gridDelta=params["gridDelta"],
    xExtent=params["xExtent"],
    yExtent=params["yExtent"],
)
ps.MakeTrench(
    domain=geometry,
    trenchWidth=params["trenchWidth"],
    trenchDepth=0.0,
    maskHeight=params["maskHeight"],
).apply()


direction = [0.0, 0.0, 0.0]
direction[args.dim - 1] = -1.0

# Geometric advection model for deposition
depoModel = ps.SphereDistribution(radius=params["depositionThickness"])

# Define purely directional rate for depo removal
etchDir = ps.RateSet(
    direction=direction,
    directionalVelocity=-(params["depositionThickness"] + params["gridDelta"] / 2.0),
    isotropicVelocity=0.0,
    maskMaterials=[ps.Material.Mask],
)
depoRemoval = ps.DirectionalProcess(rateSets=[etchDir])

# Define isotropic + direction rate for etching of substrate
etchIso = ps.RateSet(
    direction=direction,
    directionalVelocity=params["ionRate"],
    isotropicVelocity=params["neutralRate"],
    maskMaterials=[ps.Material.Mask, ps.Material.Polymer],
)
etchModel = ps.DirectionalProcess(rateSets=[etchIso])
etchTime = params["etchTime"]

def runProcess(model, name, time=1.0):
    print("  - {} - ".format(name))
    ps.Process(geometry, model, time).apply()


numCycles = int(params["numCycles"])

runProcess(etchModel, "Etching", etchTime)

for i in range(numCycles):
    print("Cycle {}".format(i + 1))

    # Deposit a layer of polymer
    geometry.duplicateTopLevelSet(ps.Material.Polymer)
    runProcess(depoModel, "Deposition")

    # Remove the polymer layer
    runProcess(depoRemoval, "Punching through")

    # Etch the trench
    runProcess(etchModel, "Etching", etchTime)

    # Ash (remove) the polymer
    geometry.removeTopLevelSet()
    geometry.removeStrayPoints()

lsmesh.mesh(geometry, "mesh.vtu", dimension=args.dim)


