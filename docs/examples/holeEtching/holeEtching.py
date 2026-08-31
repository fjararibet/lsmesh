from argparse import ArgumentParser
import viennaps as ps

import lsmesh

# parse config file name and simulation dimension
parser = ArgumentParser(prog="holeEtching", description="Run a hole etching process.")
parser.add_argument("-D", "-DIM", dest="dim", type=int, default=2)
parser.add_argument("filename")
args = parser.parse_args()

# switch between 2D and 3D mode
if args.dim == 2:
    print("Running 2D simulation.")
else:
    print("Running 3D simulation.")
ps.setDimension(args.dim)
ps.setNumThreads(16)

params = ps.readConfigFile(args.filename)

unit_aliases = {
    "um": "micrometer",
    "nm": "nanometer",
    "mm": "millimeter",
    "cm": "centimeter",
    "m": "meter",
    "min": "minute",
    "s": "second",
}
spatial_scheme_aliases = {
    "EO_1": "ENGQUIST_OSHER_1ST_ORDER",
    "EO_2": "ENGQUIST_OSHER_2ND_ORDER",
    "LF_1": "LAX_FRIEDRICHS_1ST_ORDER",
    "LF_2": "LAX_FRIEDRICHS_2ND_ORDER",
    "LLF_1": "LOCAL_LAX_FRIEDRICHS_1ST_ORDER",
    "LLF_2": "LOCAL_LAX_FRIEDRICHS_2ND_ORDER",
    "SLLF_1": "STENCIL_LOCAL_LAX_FRIEDRICHS_1ST_ORDER",
    "WENO3": "WENO_3RD_ORDER",
    "WENO5": "WENO_5TH_ORDER",
}
temporal_scheme_aliases = {
    "FE": "FORWARD_EULER",
    "RK2": "RUNGE_KUTTA_2ND_ORDER",
    "RK3": "RUNGE_KUTTA_3RD_ORDER",
}

length_unit = str(params["lengthUnit"]).strip()
time_unit = str(params["timeUnit"]).strip()
ps.Length.setUnit(unit_aliases.get(length_unit, length_unit))
ps.Time.setUnit(unit_aliases.get(time_unit, time_unit))


def run_simulation(intermediate_velocities):
    # geometry setup, all units in um
    geometry = ps.Domain(
        gridDelta=params["gridDelta"],
        xExtent=params["xExtent"],
        yExtent=params["yExtent"],
    )

    ps.MakeHole(
        domain=geometry,
        holeRadius=params["holeRadius"],
        holeDepth=0.0,
        maskHeight=params["maskHeight"],
        maskTaperAngle=params["taperAngle"],
        holeShape=ps.HoleShape.QUARTER,
    ).apply()

    # use pre-defined model SF6O2 etching model
    modelParams = ps.SF6O2Etching.defaultParameters()
    modelParams.ionFlux = params["ionFlux"]
    modelParams.etchantFlux = params["etchantFlux"]
    modelParams.passivationFlux = params["oxygenFlux"]
    modelParams.Ions.meanEnergy = params["meanEnergy"]
    modelParams.Ions.sigmaEnergy = params["sigmaEnergy"]
    modelParams.Ions.exponent = params["ionExponent"]
    modelParams.Passivation.A_ie = params["A_O"]
    modelParams.Substrate.A_ie = params["A_Si"]
    modelParams.etchStopDepth = params["etchStopDepth"]
    model = ps.SF6O2Etching(modelParams)

    covParams = ps.CoverageParameters()
    covParams.tolerance = 1e-4

    rayParams = ps.RayTracingParameters()
    rayParams.raysPerPoint = int(params["raysPerPoint"])

    advParams = ps.AdvectionParameters()
    spatial_scheme = str(params["spatialScheme"]).strip()
    temporal_scheme = str(params["temporalScheme"]).strip()
    advParams.spatialScheme = ps.util.convertSpatialScheme(
        spatial_scheme_aliases.get(spatial_scheme, spatial_scheme)
    )
    advParams.temporalScheme = ps.util.convertTemporalScheme(
        temporal_scheme_aliases.get(temporal_scheme, temporal_scheme)
    )
    advParams.calculateIntermediateVelocities = intermediate_velocities

    # process setup
    process = ps.Process(geometry, model)
    process.setProcessDuration(params["processTime"])  # seconds
    process.setParameters(covParams)
    process.setParameters(rayParams)
    process.setParameters(advParams)

    fluxEngineStr = str(params["fluxEngine"]).strip()
    fluxEngine = ps.util.convertFluxEngineType(fluxEngineStr)
    process.setFluxEngineType(fluxEngine)

    # run the process
    process.apply()

    lsmesh.mesh(geometry, "mesh.vtu", dimension=args.dim)


print("Running simulation...")
run_simulation(False)



