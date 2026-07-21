import viennaps as ps

ps.setDimension(2)
ps.Logger.setLogLevel(ps.LogLevel.WARNING)


def generateSimpleGeometry(gridDelta=1.0, saveFiles=True):

    geometry = ps.Domain(gridDelta=gridDelta, xExtent=50)
    ps.MakeFin(
        domain=geometry,
        finWidth=10,
        finHeight=0,
        material=ps.Material.Si,
        maskHeight=20,
        maskMaterial=ps.Material.SiO2,
    ).apply()

    geometry.duplicateTopLevelSet(ps.Material.Si3N4)
    geoDep = ps.SphereDistribution(radius=5)
    ps.Process(geometry, geoDep).apply()

    if saveFiles:
        geometry.saveSurfaceMesh("Simple_2D", addInterfaces=True)
        geometry.saveVolumeMesh("Simple_2D")

    matMap = geometry.getMaterialMap()
    for i in range(len(geometry.getLevelSets())):
        mat = matMap.getMaterialAtIdx(i)
        print("Material at index", i, "is", matMap.toString(mat), "id:", mat)
    for i, levelSet in enumerate(geometry.getLevelSets()):
        mesh = ps.ls.Mesh()
        ps.ls.ToSurfaceMesh(levelSet, mesh).apply()
        ps.ls.VTKWriter(mesh, f"interface_{i}").apply()

    return geometry.getSurfaceMesh(addInterfaces=True)


def main():
    mesh = generateSimpleGeometry(gridDelta=0.35, saveFiles=True)

    # access mesh data
    nodes = mesh.getNodes()
    elements = mesh.getLines()

    # modify or add mesh data as needed
    # ...

    # save mesh to file
    ps.ls.VTKWriter(mesh, "Simple_2D_Output.vtp").apply()


if __name__ == "__main__":
    main()
