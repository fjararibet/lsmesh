"""3D polygon I/O utilities for reading and writing mesh files."""

from collections.abc import Sequence
from pathlib import Path

import vtk

from lsmesher.geometry_types import Edge, Face, Point3D, Region3D


def read_poly(
    filename: str | Path,
) -> tuple[list[Point3D], list[Edge]]:
    """Read a 3D polygon from a POLY file.

    Args:
        filename: Path to the POLY file.

    Returns:
        Tuple of (points, edges) where points are (x, y, z) coordinates
        and edges are (i, j) tuples indexing into points.
    """
    with Path(filename).open() as f:
        point_count = int(f.readline().split()[0])
        points: list[Point3D] = []
        for _ in range(point_count):
            p_info = [float(x) for x in f.readline().split()]
            points.append(Point3D(p_info[1], p_info[2], p_info[3]))

        edges_count = int(f.readline().split()[0])
        edges: list[Edge] = []
        for _ in range(edges_count):
            e_info = [int(x) - 1 for x in f.readline().split()]
            edges.append(Edge(e_info[1], e_info[2]))

    return points, edges


def write_poly(
    filename: str | Path,
    points: Sequence[Point3D],
    edges: Sequence[Edge],
) -> None:
    """Write a 3D polygon to a POLY file.

    Args:
        filename: Path to the output file.
        points: List of (x, y, z) coordinates.
        edges: List of edge tuples (i, j).
    """
    with Path(filename).open("w") as f:
        f.write(f"{len(points)} 3 0 0\n")
        f.writelines(
            f"{i + 1} {points[i].x} {points[i].y} {points[i].z}\n"
            for i in range(len(points))
        )

        f.write(f"{len(edges)} 0\n")
        f.writelines(
            f"{i + 1} {edges[i].start + 1} {edges[i].end + 1}\n"
            for i in range(len(edges))
        )
        f.write("0\n0")


def read_vtp_points(vtp_file: str | Path) -> list[Point3D]:
    """Read 3D points from a VTP (VTK PolyData) file.

    Args:
        vtp_file: Path to the VTP file.

    Returns:
        List of (x, y, z) coordinates.
    """
    reader = vtk.vtkXMLPolyDataReader()
    reader.SetFileName(str(vtp_file))
    reader.Update()
    polydata = reader.GetOutput()
    points_vtk = polydata.GetPoints()

    return [
        Point3D(*points_vtk.GetPoint(i)) for i in range(points_vtk.GetNumberOfPoints())
    ]


def read_vtp_edges(vtp_file: str | Path) -> list[Edge]:
    """Read edges from a VTP (VTK PolyData) file.

    Args:
        vtp_file: Path to the VTP file.

    Returns:
        List of edge tuples (i, j).
    """
    reader = vtk.vtkXMLPolyDataReader()
    reader.SetFileName(str(vtp_file))
    reader.Update()
    polydata = reader.GetOutput()

    lines = polydata.GetLines()
    lines.InitTraversal()
    id_list = vtk.vtkIdList()

    edges: list[Edge] = []
    while lines.GetNextCell(id_list):
        edges.append(Edge(id_list.GetId(0), id_list.GetId(1)))

    return edges


def read_vtp_faces(vtp_file: str | Path) -> list[Face]:
    """Read faces from a VTP (VTK PolyData) file.

    Args:
        vtp_file: Path to the VTP file.

    Returns:
        List of faces, where each face is a list of vertex indices.
    """
    reader = vtk.vtkXMLPolyDataReader()
    reader.SetFileName(str(vtp_file))
    reader.Update()
    polydata = reader.GetOutput()

    polys = polydata.GetPolys()
    polys.InitTraversal()
    id_list = vtk.vtkIdList()

    faces: list[Face] = []
    while polys.GetNextCell(id_list):
        face = Face(tuple(id_list.GetId(i) for i in range(id_list.GetNumberOfIds())))
        faces.append(face)

    return faces


def load_off(
    path: str | Path,
) -> tuple[list[Point3D], list[Face]]:
    """Load an OFF file and return (points, faces).

    Args:
        path: Path to the OFF file.

    Returns:
        Tuple of (points, faces) where points are [x, y, z] floats
        and faces are lists of vertex indices.
    """
    with Path(path).open() as f:
        # Read first non-empty, non-comment line
        line = f.readline().strip()
        while line == "" or line.startswith("#"):
            line = f.readline().strip()

        # Read counts: n_vertices, n_faces, n_edges
        line = f.readline().strip()
        while line == "" or line.startswith("#"):
            line = f.readline().strip()

        n_verts, n_faces, _ = map(int, line.split())

        # Read vertices
        points: list[Point3D] = []
        for _ in range(n_verts):
            line = f.readline().strip()
            while line == "" or line.startswith("#"):
                line = f.readline().strip()
            points.append(Point3D(*map(float, line.split()[:3])))

        # Read faces
        faces: list[Face] = []
        for _ in range(n_faces):
            line = f.readline().strip()
            while line == "" or line.startswith("#"):
                line = f.readline().strip()
            parts = list(map(int, line.split()))
            k = parts[0]
            faces.append(Face(tuple(parts[1 : 1 + k])))

    return points, faces


def vtp_to_poly_string(  # noqa: PLR0913
    points: Sequence[Point3D],
    faces: Sequence[Face],
    holes: Sequence[Point3D] | None = None,
    regions: Sequence[Region3D] | None = None,
    attributes: Sequence[float] | None = None,
    facets: Sequence[Sequence[Face]] | None = None,
) -> str:
    """Convert a 3D mesh to a TetGen .poly formatted string.

    Args:
        points: List of (x, y, z) coordinates.
        faces: List of faces, each face is a list of vertex indices (0-based).
        holes: Optional list of hole points.
        regions: Optional list of material region points.
        attributes: Optional list of per-point attributes.
        facets: Optional multi-polygon facets. Each facet is a group of
            polygons; two-vertex polygons are segments constraining the
            facet's triangulation.

    Returns:
        The TetGen POLY format string.
    """
    holes = holes or []
    regions = regions or []
    attributes = attributes or []
    facets = facets or []
    lines = []

    # Part 1: Node list
    lines.append(f"{len(points)} 3 {len(attributes)} 0")
    for i, point in enumerate(points):
        lines.append(f"{i + 1} {point.x} {point.y} {point.z}")

    polygon_facets = [face for face in faces if len(face.vertices) >= 3]

    # Part 2: Facet list
    lines.append(f"{len(polygon_facets) + len(facets)} 0 # faces")

    for face in polygon_facets:
        corners = " ".join(str(idx + 1) for idx in face.vertices)
        lines.append("1 0")
        lines.append(f"{len(face.vertices)} {corners}")

    for facet in facets:
        lines.append(f"{len(facet)} 0")
        for polygon in facet:
            corners = " ".join(str(idx + 1) for idx in polygon.vertices)
            lines.append(f"{len(polygon.vertices)} {corners}")

    # Part 3: Hole list
    lines.append(f"{len(holes)}")
    for i, point in enumerate(holes):
        lines.append(f"{i + 1} {point.x} {point.y} {point.z}")

    # Part 4: Region attribute list
    lines.append(f"{len(regions)}")
    for i, region in enumerate(regions):
        point = region.point
        lines.append(f"{i + 1} {point.x} {point.y} {point.z} {region.material} -1")

    return "\n".join(lines)


def to_off_string(points: Sequence[Point3D], faces: Sequence[Face]) -> str:
    """Convert points and faces to an OFF (Object File Format) string.

    Args:
        points: List of (x, y, z) coordinates.
        faces: List of faces, each face is a list of vertex indices (0-based).

    Returns:
        The OFF format string.
    """
    lines = ["OFF"]

    num_vertices = len(points)
    num_faces = len(faces)
    num_edges = 0  # can be 0 if we don't want to count

    lines.append(f"{num_vertices} {num_faces} {num_edges}")

    # Vertices
    lines.extend(f"{point.x} {point.y} {point.z}" for point in points)

    # Faces
    for face in faces:
        k = len(face.vertices)
        indices = " ".join(str(idx) for idx in face.vertices)
        lines.append(f"{k} {indices}")

    return "\n".join(lines)


def read_tetgen_mesh(
    basename: str | Path,
) -> tuple[list[Point3D], list[Face], list[int]]:
    """Read TetGen tetrahedral output files with material attributes."""
    basename = Path(basename)
    node_file = basename.parent / f"{basename.name}.1.node"
    ele_file = basename.parent / f"{basename.name}.1.ele"

    points: list[Point3D] = []
    with node_file.open() as f:
        point_count = int(f.readline().split()[0])
        for _ in range(point_count):
            parts = f.readline().split()
            points.append(Point3D(float(parts[1]), float(parts[2]), float(parts[3])))

    tetrahedra: list[Face] = []
    attributes: list[int] = []
    with ele_file.open() as f:
        header = f.readline().split()
        element_count = int(header[0])
        attribute_count = int(header[2]) if len(header) > 2 else 0
        for _ in range(element_count):
            parts = f.readline().split()
            tetrahedra.append(Face(tuple(int(vertex) - 1 for vertex in parts[1:5])))
            if attribute_count > 0 and len(parts) > 5:
                attributes.append(int(float(parts[5])))

    return points, tetrahedra, attributes


def write_vtu(
    filename: str | Path,
    points: Sequence[Point3D],
    tetrahedra: Sequence[Face],
    attributes: Sequence[int] | None = None,
) -> None:
    """Write a TetGen tetrahedral mesh to VTU with material cell data."""
    vtk_points = vtk.vtkPoints()
    for point in points:
        vtk_points.InsertNextPoint(point.x, point.y, point.z)

    cells = vtk.vtkCellArray()
    for tetrahedron_indices in tetrahedra:
        tetrahedron = vtk.vtkTetra()
        for index, vertex in enumerate(tetrahedron_indices.vertices):
            tetrahedron.GetPointIds().SetId(index, vertex)
        cells.InsertNextCell(tetrahedron)

    grid = vtk.vtkUnstructuredGrid()
    grid.SetPoints(vtk_points)
    grid.SetCells(vtk.VTK_TETRA, cells)

    if attributes:
        material_array = vtk.vtkIntArray()
        material_array.SetName("Material")
        for attribute in attributes:
            material_array.InsertNextValue(attribute)
        grid.GetCellData().AddArray(material_array)
        grid.GetCellData().SetActiveScalars("Material")

    writer = vtk.vtkXMLUnstructuredGridWriter()
    writer.SetFileName(str(filename))
    writer.SetInputData(grid)
    writer.Write()


def write_vtp(
    filename: str | Path,
    points: Sequence[Point3D],
    faces: Sequence[Face],
) -> None:
    """Write points and faces to a VTP (VTK PolyData) file.

    Args:
        filename: Path to the output VTP file.
        points: List of (x, y, z) coordinates.
        faces: List of faces, each face is a list of vertex indices.
    """
    # Create VTK points
    vtk_points = vtk.vtkPoints()
    for point in points:
        vtk_points.InsertNextPoint(point.x, point.y, point.z)

    # Create VTK polygons from faces
    polys = vtk.vtkCellArray()
    for face in faces:
        polygon = vtk.vtkPolygon()
        polygon.GetPointIds().SetNumberOfIds(len(face.vertices))
        for i, idx in enumerate(face.vertices):
            polygon.GetPointIds().SetId(i, idx)
        polys.InsertNextCell(polygon)

    # Create polydata
    polydata = vtk.vtkPolyData()
    polydata.SetPoints(vtk_points)
    polydata.SetPolys(polys)

    # Write to file
    writer = vtk.vtkXMLPolyDataWriter()
    writer.SetFileName(str(filename))
    writer.SetInputData(polydata)
    writer.Write()
