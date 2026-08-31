from argparse import ArgumentParser
import viennaps as ps

import lsmesh

# parse config file name and simulation dimension
parser = ArgumentParser(
    prog="faradayCageEtching", description="Run a faraday cage etching process."
)
parser.add_argument("-D", "-DIM", dest="dim", type=int, default=2)
args = parser.parse_args()


# switch between 2D and 3D mode
if args.dim == 2:
    print("Running 2D simulation.")
else:
    print("Running 3D simulation.")
ps.setDimension(args.dim)
params = {
    "gridDelta": 0.25,
    "xExtent": 10.0,
    "yExtent": 10.0,
    "finWidth": 2.0,
    "maskHeight": 0.5,
    "tiltAngle": 60.0,
    "cageAngle": 90.0,
    "etchTime": 0.5,
}

# print intermediate output surfaces during the process
ps.Logger.setLogLevel(ps.LogLevel.INFO)
ps.setNumThreads(16)

# geometry setup, all units in um
geometry = ps.Domain(
    gridDelta=params["gridDelta"],
    xExtent=params["xExtent"],
    yExtent=params["yExtent"],
    boundary=ps.BoundaryType.PERIODIC_BOUNDARY,
)
ps.MakeFin(
    domain=geometry,
    finWidth=params["finWidth"],
    finHeight=0.0,
    maskHeight=params["maskHeight"],
).apply()

# use pre-defined etching model
parameters = ps.FaradayCageParameters()
parameters.cageAngle = params["cageAngle"]
parameters.ibeParams.tiltAngle = params["tiltAngle"]
mask = [ps.Material.Mask]

model = ps.FaradayCageEtching(parameters, mask)

advParams = ps.AdvectionParameters()
advParams.spatialScheme = ps.SpatialScheme.LAX_FRIEDRICHS_1ST_ORDER

# process setup
process = ps.Process()
process.setDomain(geometry)
process.setProcessModel(model)
process.setParameters(advParams)
process.setProcessDuration(params["etchTime"])  # seconds

# run the process
process.apply()

lsmesh.mesh(geometry, "mesh.vtu", dimension=args.dim)


