import viennaps as vps

vps.setDimension(2)
vps.Logger.setLogLevel(vps.LogLevel.WARNING)

gridDelta = 0.1
extent = 20.0
geometry = vps.Domain(
    gridDelta=gridDelta, xExtent=extent, boundary=vps.BoundaryType.REFLECTIVE_BOUNDARY
)

vps.MakeStack(
    domain=geometry,
    numLayers=5,
    layerHeight=2.0,
    substrateHeight=1.0,
    trenchWidth=8.0,
    maskHeight=3,
    taperAngle=10.0,
).apply()

print("Creating trench ...")
directionalEtch = vps.DirectionalProcess(
    direction=[0.0, -1.0, 0.0],
    directionalVelocity=-1.0,
    maskMaterial=vps.Material.Mask,
    calculateVisibility=False,
)
vps.Process(geometry, directionalEtch, 12).apply()

print("Adding polymer ...")
geometry.duplicateTopLevelSet(vps.Material.Polymer)
addLayer = vps.IsotropicProcess(rate=1.0)
vps.Process(geometry, addLayer, 0.5).apply()

print("Removing polymer partly ...")
removeLayer = vps.SingleParticleProcess(
    rate=-1.0, stickingProbability=1.0, sourceExponent=1
)
vps.Process(geometry, removeLayer, 2.0).apply()

# Finished geometry processing
print("Finished geometry processing")

# export geometry
geometry.saveVolumeMesh("geometry")  # volume mesh (don't use for meshing)

# Extract interfaces as lines
# Loop starts at bottom and goes to top
for i, levelSet in enumerate(geometry.getLevelSets()):
    mesh = vps.ls.Mesh()
    vps.ls.ToSurfaceMesh(levelSet, mesh).apply()
    vps.ls.VTKWriter(mesh, f"interface_{i}").apply()
