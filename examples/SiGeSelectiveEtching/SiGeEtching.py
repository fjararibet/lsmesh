from argparse import ArgumentParser

import viennaps as ps
from SiGeStackGeometry import CreateGeometry

import lsmesh


parser = ArgumentParser(description="Run selective SiGe stack etching.")
parser.add_argument("-D", "-DIM", dest="dim", type=int, default=2)
parser.add_argument("filename")
args = parser.parse_args()
if args.dim != 2:
    raise ValueError("SiGe Selective Etching only supports 2D generation")

ps.setDimension(args.dim)
ps.setNumThreads(16)

# create initial geometry
paramDict = {
    "numPillars": 3,
    "numLayers": 12,
    "layerHeight": 20.0,
    "maskWidth": 100.0,
    "maskHeight": 55.0,
    "trenchWidthTop": 100.0,
    "trenchWidthBottom": 100.0,
    "overEtch": 100.0,
    "lateralSpacing": 300.0,
    "periodicBoundary": False,
    "gridDelta": 2.5,
}
geometry = CreateGeometry(paramDict)

params = ps.readConfigFile(args.filename)

ps.Logger.setLogLevel(ps.LogLevel.INFO)

ps.Length.setUnit(params["lengthUnit"])
ps.Time.setUnit(params["timeUnit"])

# use pre-defined model CF4O2 etching model
modelParams = ps.CF4O2Parameters()
modelParams.ionFlux = params["ionFlux"]
modelParams.etchantFlux = params["etchantFlux"]
modelParams.oxygenFlux = params["oxygenFlux"]
modelParams.polymerFlux = params["polymerFlux"]
modelParams.Ions.meanEnergy = params["meanEnergy"]
modelParams.Ions.sigmaEnergy = params["sigmaEnergy"]
modelParams.Passivation.A_O_ie = params["A_O"]
modelParams.Passivation.A_C_ie = params["A_C"]

# Use Material enum
modelParams.gamma_F.set(ps.Material.Mask, 0.0)
modelParams.gamma_F.set(ps.Material.Si, 0.1)
modelParams.gamma_F.set(ps.Material.SiGe, 0.1)

modelParams.gamma_F_oxidized.set(ps.Material.Mask, 0.0)
modelParams.gamma_F_oxidized.set(ps.Material.Si, 0.1)
modelParams.gamma_F_oxidized.set(ps.Material.SiGe, 0.1)

modelParams.gamma_O.set(ps.Material.Mask, 0.0)
modelParams.gamma_O.set(ps.Material.Si, 0.7)
modelParams.gamma_O.set(ps.Material.SiGe, 0.7)

modelParams.gamma_O_passivated.set(ps.Material.Mask, 0.0)
modelParams.gamma_O_passivated.set(ps.Material.Si, 0.7)
modelParams.gamma_O_passivated.set(ps.Material.SiGe, 0.7)

modelParams.gamma_C.set(ps.Material.Mask, 0.0)
modelParams.gamma_C.set(ps.Material.Si, 0.7)
modelParams.gamma_C.set(ps.Material.SiGe, 0.7)

modelParams.gamma_C_oxidized.set(ps.Material.Mask, 0.0)
modelParams.gamma_C_oxidized.set(ps.Material.Si, 0.7)
modelParams.gamma_C_oxidized.set(ps.Material.SiGe, 0.7)

model = ps.CF4O2Etching(modelParams)
parameters = model.getParameters()

covParams = ps.CoverageParameters()
covParams.maxIterations = 20
covParams.tolerance = 1e-4

rayParams = ps.RayTracingParameters()
rayParams.raysPerPoint = int(params["raysPerPoint"])

advParams = ps.AdvectionParameters()
advParams.timeStepRatio = 0.2

# process setup
process = ps.Process()
process.setDomain(geometry)
process.setProcessModel(model)
process.setProcessDuration(params["processTime"])  # seconds
process.setParameters(covParams)
process.setParameters(rayParams)
process.setParameters(advParams)

# run the process
process.apply()

lsmesh.mesh(geometry, "mesh.vtu", dimension=args.dim)



