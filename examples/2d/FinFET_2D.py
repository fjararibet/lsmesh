import viennaps as ps

ps.setDimension(2)
ps.Logger.setLogLevel(ps.LogLevel.WARNING)


def generateFinFETCrossSection(gridDelta=0.79, saveFiles=True):
    i = 0
    geometry = ps.Domain(gridDelta=gridDelta, xExtent=100)

    ps.MakePlane(domain=geometry, height=70, material=ps.Material.Si).apply()
    if saveFiles:
        geometry.saveSurfaceMesh(f"FinFET_2D_{i}", addInterfaces=True)
    i += 1

    ps.MakePlane(
        domain=geometry, height=72, material=ps.Material.Si3N4, addToExisting=True
    ).apply()
    if saveFiles:
        geometry.saveSurfaceMesh(f"FinFET_2D_{i}", addInterfaces=True)
    i += 1

    ps.MakePlane(
        domain=geometry, height=74, material=ps.Material.HfO2, addToExisting=True
    ).apply()
    if saveFiles:
        geometry.saveSurfaceMesh(f"FinFET_2D_{i}", addInterfaces=True)
    i += 1

    ps.MakePlane(
        domain=geometry, height=150, material=ps.Material.PolySi, addToExisting=True
    ).apply()
    if saveFiles:
        geometry.saveSurfaceMesh(f"FinFET_2D_{i}", addInterfaces=True)
    i += 1

    boxMin = [-20, 150]
    boxMax = [20, 170]
    boxLS = ps.ls.Domain(geometry.getGrid())
    ps.ls.MakeGeometry(boxLS, ps.ls.Box(boxMin, boxMax)).apply()
    geoMask = ps.ls.Domain(boxLS)

    geometry.insertNextLevelSetAsMaterial(boxLS, ps.Material.Mask)
    if saveFiles:
        geometry.saveSurfaceMesh(f"FinFET_2D_{i}", addInterfaces=True)
    i += 1

    ps.ls.BooleanOperation(
        geoMask, geometry.getLevelSets()[0], ps.ls.BooleanOperationEnum.UNION
    ).apply()
    geoEtch = ps.BoxDistribution(halfAxes=[-gridDelta, -80, -gridDelta], mask=geoMask)
    ps.Process(geometry, geoEtch).apply()
    if saveFiles:
        geometry.saveSurfaceMesh(f"FinFET_2D_{i}", addInterfaces=True)
    i += 1

    geometry.removeTopLevelSet()
    geometry.duplicateTopLevelSet(ps.Material.SiN)

    geoDep = ps.SphereDistribution(radius=10)
    ps.Process(geometry, geoDep).apply()
    if saveFiles:
        geometry.saveSurfaceMesh(f"FinFET_2D_{i}", addInterfaces=True)
    i += 1

    dirModel = ps.DirectionalProcess(
        direction=[0, 1, 0], directionalVelocity=1, calculateVisibility=False
    )
    ps.Process(geometry, dirModel, 10).apply()
    if saveFiles:
        geometry.saveSurfaceMesh(f"FinFET_2D_{i}", addInterfaces=True)
    i += 1

    rateSet = ps.RateSet()
    rateSet.direction = [0, 1, 0]
    rateSet.directionalVelocity = 1
    rateSet.isotropicVelocity = 0.1
    rateSet.maskMaterials = [ps.Material.SiN, ps.Material.PolySi]
    rateSet.calculateVisibility = False
    finEtch = ps.DirectionalProcess(rateSet=rateSet)
    ps.Process(geometry, finEtch, 25).apply()
    if saveFiles:
        geometry.saveSurfaceMesh(f"FinFET_2D_{i}", addInterfaces=True)
    i += 1

    epi = ps.SelectiveEpitaxy(
        materialRates=[(ps.Material.Si, 1.0), (ps.Material.SiGe, 1.0)],
        rate111=0.1,
        rate100=2.0,
    )
    geometry.duplicateTopLevelSet(ps.Material.SiGe)
    advectionParams = ps.AdvectionParameters()
    advectionParams.spatialScheme = (
        ps.SpatialScheme.STENCIL_LOCAL_LAX_FRIEDRICHS_1ST_ORDER
    )
    ps.StencilLocalLaxFriedrichsScalar.setMaxDissipation(1000)

    process = ps.Process(geometry, epi, 7.0)
    process.setParameters(advectionParams)
    process.apply()
    if saveFiles:
        geometry.saveSurfaceMesh(f"FinFET_2D_{i}", addInterfaces=True)
    i += 1

    ps.MakePlane(
        domain=geometry, height=150, material=ps.Material.SiO2, addToExisting=True
    ).apply()
    geometry.removeMaterial(ps.Material.PolySi)
    if saveFiles:
        geometry.saveSurfaceMesh(f"FinFET_2D_{i}", addInterfaces=True)
    i += 1

    geometry.duplicateTopLevelSet(ps.Material.TiN)
    geoDep = ps.SphereDistribution(radius=5)
    ps.Process(geometry, geoDep).apply()
    if saveFiles:
        geometry.saveSurfaceMesh(f"FinFET_2D_{i}", addInterfaces=True)
    i += 1

    ps.Planarize(geometry=geometry, cutoffHeight=150).apply()
    if saveFiles:
        geometry.saveSurfaceMesh(f"FinFET_2D_{i}", addInterfaces=True)
    i += 1

    ps.MakePlane(
        domain=geometry, height=150, material=ps.Material.W, addToExisting=True
    ).apply()
    if saveFiles:
        geometry.saveSurfaceMesh(f"FinFET_2D_{i}", addInterfaces=True)
    i += 1

    matMap = geometry.getMaterialMap()
    for i in range(len(geometry.getLevelSets())):
        mat = matMap.getMaterialAtIdx(i)
        print("Material at index", i, "is", matMap.toString(mat), "id:", mat)

    if saveFiles:
        geometry.saveVolumeMesh("FinFET_2D_final")
    return geometry.getSurfaceMesh(addInterfaces=True)


def main():
    mesh = generateFinFETCrossSection(gridDelta=0.65, saveFiles=True)

    # access mesh data
    nodes = mesh.getNodes()
    elements = mesh.getLines()

    # modify or add mesh data as needed
    # ...

    # save mesh to file
    ps.ls.VTKWriter(mesh, "FinFET_2D_Output.vtp").apply()


if __name__ == "__main__":
    main()
