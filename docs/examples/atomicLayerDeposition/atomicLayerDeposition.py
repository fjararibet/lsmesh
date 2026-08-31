from argparse import ArgumentParser

import viennaps as ps
import viennals as ls

import lsmesh


parser = ArgumentParser(description="Run atomic layer deposition.")
parser.add_argument("-D", "-DIM", dest="dim", type=int, default=2)
args = parser.parse_args()
if args.dim != 2:
    raise ValueError("Atomic Layer Deposition only supports 2D generation")
ps.setDimension(args.dim)
ls.setDimension(args.dim)

config = {
    "gridDelta": 0.1,
    "openingDepth": 0.5,
    "openingWidth": 90,
    "gapLength": 800,
    "gapHeight": 0.5,
    "gapWidth": 10000,
    "xPad": 0.5,
    "topSpace": 0.0,
    "pulseTime": 0.1,
    "purgePulseTime": 0.05,
    "coverageTimeStep": 0.01,
    "growthPerCycle": 0.000112,
    "numCycles": 10,
    "totalCycles": 800,
    "pressure": 0.1,
    "temperature": 220,
    "diameter": 2.75,
    "mass": 28.02,
    "inFlux": 2e6,
    "stickingProbability": 5e-5,
    "evFlux": 2.5,
    "s0": 3.36,
    "numRaysPerPoint": 1000,
    "rngSeed": 15123512,
    "outputFile": "arts_220_c8.txt",
}
geometry = ps.Domain()

# Create the geometry
boundaryCons = [
    ps.BoundaryType.REFLECTIVE_BOUNDARY,
    ps.BoundaryType.INFINITE_BOUNDARY,
]
gridDelta = config["gridDelta"]
bounds = [
    0.0,
    config["openingWidth"] / 2.0 + config["xPad"] + config["gapLength"],
    -gridDelta,
    config["openingDepth"] + config["gapHeight"] + gridDelta,
]

substrate = ls.Domain(bounds, boundaryCons, gridDelta)
normal = [0.0, 1.0]
origin = [0.0, config["openingDepth"] + config["gapHeight"]]
ls.MakeGeometry(substrate, ls.Plane(origin, normal)).apply()

geometry.insertNextLevelSetAsMaterial(substrate, ps.Material.Si)

vertBox = ls.Domain(bounds, boundaryCons, gridDelta)
minPoint = [-gridDelta, 0.0]
maxPoint = [
    config["openingWidth"] / 2.0,
    config["gapHeight"] + config["openingDepth"] + gridDelta,
]
ls.MakeGeometry(vertBox, ls.Box(minPoint, maxPoint)).apply()

geometry.applyBooleanOperation(vertBox, ls.BooleanOperationEnum.RELATIVE_COMPLEMENT)

horiBox = ls.Domain(bounds, boundaryCons, gridDelta)
minPoint = [config["openingWidth"] / 2.0 - gridDelta, 0.0]
maxPoint = [config["openingWidth"] / 2.0 + config["gapLength"], config["gapHeight"]]
ls.MakeGeometry(horiBox, ls.Box(minPoint, maxPoint)).apply()
geometry.applyBooleanOperation(horiBox, ls.BooleanOperationEnum.RELATIVE_COMPLEMENT)

geometry.duplicateTopLevelSet(ps.Material.Al2O3)

gasMFP = ps.constants.gasMeanFreePath(
    config["pressure"], config["temperature"], config["diameter"]
)
print("Mean free path: ", gasMFP, " um")

gpc = config["totalCycles"] / config["numCycles"] * config["growthPerCycle"]

model_params = ps.SingleParticleALDParams()
model_params.stickingProbability = config["stickingProbability"]
model_params.gasMeanFreePath = gasMFP
model_params.growthPerCycle = gpc
model_params.evaporationFlux = config["evFlux"]
model_params.incomingFlux = config["inFlux"]
model_params.s0 = config["s0"]

model = ps.SingleParticleALD(model_params)

alpParams = ps.AtomicLayerProcessParameters()
alpParams.pulseTime = config["pulseTime"]
alpParams.coverageTimeStep = config["coverageTimeStep"]
alpParams.numCycles = int(config["numCycles"])

rayParams = ps.RayTracingParameters()
rayParams.raysPerPoint = int(config["numRaysPerPoint"])

ALP = ps.Process(geometry, model)
ALP.setParameters(rayParams)
ALP.setParameters(alpParams)
ALP.apply()

# ## TODO: Implement MeasureProfile in Python
# #   MeasureProfile<NumericType, D>(domain, params.get("gapHeight") / 2.)
# #       .save(params.get<std::string>("outputFile"));

lsmesh.mesh(geometry, "mesh.vtu", dimension=args.dim)


