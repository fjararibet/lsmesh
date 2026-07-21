import viennaps as vps

vps.setDimension(3)
vps.Logger.setLogLevel(vps.LogLevel.INFO)

gridDelta = 2.0
extent = 20.0
geometry = vps.Domain(
    gridDelta=gridDelta,
    xExtent=extent,
    yExtent=extent,
    boundary=vps.BoundaryType.REFLECTIVE_BOUNDARY,
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
    direction=[0.0, 0.0, -1.0],
    directionalVelocity=-1.0,
    maskMaterial=vps.Material.Mask,
    calculateVisibility=False,
)
process_time = 12
# process = vps.Process(geometry, directionalEtch, 12)
vps.Process(domain=geometry, model=directionalEtch, duration=process_time).apply()

print("Adding polymer ...")
geometry.duplicateTopLevelSet(vps.Material.Polymer)
addLayer = vps.IsotropicProcess(rate=1.0)
vps.Process(geometry, addLayer, 0.5).apply()

print("Removing polymer partly ...")
removeLayer = vps.SingleParticleProcess(
    rate=-1.0, stickingProbability=1.0, sourceExponent=1
)
process_time = 6.0
vps.Process(geometry, removeLayer, process_time).apply()

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
    mm = vps.ls.MaterialMap()
    print(f"interface_{i}, material_id: {mm.getMaterialId(i)}")
