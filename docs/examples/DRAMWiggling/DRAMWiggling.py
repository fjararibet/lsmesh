import viennaps as ps
from argparse import ArgumentParser

import lsmesh


# parse config file name and simulation dimension
parser = ArgumentParser(
    prog="DRAMWiggling",
    description="Run a DRAM etching process which results in AA wiggling.",
)
parser.add_argument("-D", "-DIM", dest="dim", type=int, default=3)
args = parser.parse_args()

if args.dim != 3:
    raise ValueError("DRAM Wiggling only supports 3D generation")
ps.setDimension(args.dim)

gridDelta = 0.01 * (1.0 + 1e-12)
boundaryConds = [
    ps.BoundaryType.REFLECTIVE_BOUNDARY,
    ps.BoundaryType.REFLECTIVE_BOUNDARY,
    ps.BoundaryType.INFINITE_BOUNDARY,
]

params = {
    "lengthUnit": "um",
    "processTime": 1,
    "timeUnit": "second",
    "ionFlux": 10.0,
    "etchantFlux": 4.5e3,
    "oxygenFlux": 2.5e3,
    "ionExponent": 1000,
    "meanEnergy": 200,
    "sigmaEnergy": 10,
    "spatialScheme": "LF_2",
    "numSteps": 20,
    "raysPerPoint": 1000,
    "fluxEngine": "CD",
    "gdsFile": "../../viewer_presets/DRAMWiggling/wiggle_full.gds",
}

mask = ps.GDSGeometry(gridDelta, boundaryConds)
mask.setBoundaryPadding(0.1, 0.1)
reader = ps.GDSReader(mask, params["gdsFile"])
reader.apply()

# Prepare geometry
geometry = ps.Domain()

# Insert GDS layers
maskLS = mask.layerToLevelSet(0, 0.0, 0.18)
geometry.insertNextLevelSetAsMaterial(maskLS, ps.Material.Mask)

# Add plane
ps.MakePlane(geometry, 0.0, ps.Material.Si, True).apply()

ps.Length.setUnit(params["lengthUnit"])
ps.Time.setUnit(params["timeUnit"])

modelParams = ps.HBrO2Etching.defaultParameters()
modelParams.ionFlux = params["ionFlux"]
modelParams.etchantFlux = params["etchantFlux"]
modelParams.passivationFlux = params["oxygenFlux"]
modelParams.Ions.meanEnergy = params["meanEnergy"]
modelParams.Ions.sigmaEnergy = params["sigmaEnergy"]
modelParams.Ions.exponent = params["ionExponent"]
modelParams.Ions.n_l = 200
modelParams.Substrate.B_sp = 0.75
model = ps.HBrO2Etching(modelParams)

coverageParameters = ps.CoverageParameters()
coverageParameters.tolerance = 1e-5

rayTracingParams = ps.RayTracingParameters()
rayTracingParams.raysPerPoint = int(params["raysPerPoint"])

advectionParams = ps.AdvectionParameters()
advectionParams.spatialScheme = ps.util.convertSpatialScheme(params["spatialScheme"])

fluxEngineStr = params["fluxEngine"]
fluxEngine = ps.util.convertFluxEngineType(fluxEngineStr)

# process setup
process = ps.Process(geometry, model)
process.setProcessDuration(params["processTime"])  # seconds
process.setParameters(coverageParameters)
process.setParameters(rayTracingParams)
process.setParameters(advectionParams)
process.setFluxEngineType(fluxEngine)

numSteps = int(params["numSteps"])
for i in range(numSteps):
    # run the process
    process.apply()

lsmesh.mesh(geometry, "mesh.vtu", dimension=args.dim)


