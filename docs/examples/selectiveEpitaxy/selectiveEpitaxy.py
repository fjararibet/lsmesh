from argparse import ArgumentParser
import viennaps as ps

import lsmesh

# parse config file name and simulation dimension
parser = ArgumentParser(
    prog="selectiveEpitaxy",
    description="Run a selective epitaxial growth process.",
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
    "gridDelta": 0.4,
    "xExtent": 30.0,
    "yExtent": 20.0,
    "finWidth": 7.0,
    "finHeight": 10.0,
    "oxideHeight": 3.0,
    "etchTime": 4.0,
    "processTime": 5.0,
    "epitaxyRate": 2.0,
    "R111": 0.4,
    "R100": 1.0,
}

geometry = ps.Domain(
    gridDelta=params["gridDelta"], xExtent=params["xExtent"], yExtent=params["yExtent"]
)
ps.MakeFin(
    domain=geometry,
    finWidth=params["finWidth"],
    finHeight=params["finHeight"],
).apply()

ps.MakePlane(
    domain=geometry,
    height=params["oxideHeight"],
    material=ps.Material.SiO2,
    addToExisting=True,
).apply()

# copy top layer to capture deposition
geometry.duplicateTopLevelSet(ps.Material.SiGe)

model = ps.SelectiveEpitaxy(
    materialRates=[
        (ps.Material.Si, params["epitaxyRate"]),
        (ps.Material.SiGe, params["epitaxyRate"]),
    ],
    rate111=params["R111"],
    rate100=params["R100"],
)

advectionParams = ps.AdvectionParameters()
advectionParams.spatialScheme = ps.SpatialScheme.STENCIL_LOCAL_LAX_FRIEDRICHS_1ST_ORDER

process = ps.Process(geometry, model, params["processTime"])
process.setParameters(advectionParams)

process.apply()

lsmesh.mesh(geometry, "mesh.vtu", dimension=args.dim)


