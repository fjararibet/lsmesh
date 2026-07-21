"""2D polygon I/O utilities for reading and writing mesh files."""

from collections.abc import Sequence
from pathlib import Path

import vtk

from lsmesher.geometry_types import (
    Edge,
    Face,
    Point2D,
)


def read_poly(
    filename: str | Path,
) -> tuple[list[Point2D], list[Edge]]:
    """Read a 2D polygon from a POLY file.

    Args:
        filename: Path to the POLY file.

    Returns:
        Tuple of (points, edges) where points are (x, y) coordinates
        and edges are (i, j) tuples indexing into points.
    """
    with Path(filename).open() as f:
        point_count = int(f.readline().split()[0])
        points: list[Point2D] = []
        for _ in range(point_count):
            p_info = [float(x) for x in f.readline().split()]
            points.append(Point2D(p_info[1], p_info[2]))

        edges_count = int(f.readline().split()[0])
        edges: list[Edge] = []
        for _ in range(edges_count):
            e_info = [int(x) - 1 for x in f.readline().split()]
            edges.append(Edge(e_info[1], e_info[2]))

    return points, edges


def write_poly(
    filename: str | Path,
    points: Sequence[Point2D],
    edges: Sequence[Edge],
) -> None:
    """Write a 2D polygon to a POLY file.

    Args:
        filename: Path to the output file.
        points: List of (x, y) coordinates.
        edges: List of edge tuples (i, j).
    """
    with Path(filename).open("w") as f:
        f.write(f"{len(points)} 2 0 0\n")
        f.writelines(
            f"{i + 1} {points[i].x} {points[i].y}\n" for i in range(len(points))
        )

        f.write(f"{len(edges)} 0\n")
        f.writelines(
            f"{i + 1} {edges[i].start + 1} {edges[i].end + 1}\n"
            for i in range(len(edges))
        )
        f.write("0\n0")


def read_vtp_points(vtp_file: str | Path) -> tuple[list[Point2D], int, int]:
    """Read points from a VTP (VTK PolyData) file.

    Args:
        vtp_file: Path to the VTP file.

    Returns:
        Tuple of (points, leftmost_id, rightmost_id) where points are (x, y) coordinates.
    """
    reader = vtk.vtkXMLPolyDataReader()
    reader.SetFileName(str(vtp_file))
    reader.Update()
    polydata = reader.GetOutput()
    points_vtk = polydata.GetPoints()

    points = [
        Point2D(*points_vtk.GetPoint(i)[:2])  # x, y only
        for i in range(points_vtk.GetNumberOfPoints())
    ]
    leftmost_id = 0
    leftmost_point = points_vtk.GetPoint(0)
    rightmost_id = 0
    rightmost_point = points_vtk.GetPoint(0)

    for i in range(1, points_vtk.GetNumberOfPoints()):
        p = points_vtk.GetPoint(i)
        if (p[0], p[1]) < (leftmost_point[0], leftmost_point[1]):
            leftmost_id, leftmost_point = i, p[:2]
        if (p[0], p[1]) > (rightmost_point[0], rightmost_point[1]):
            rightmost_id, rightmost_point = i, p[:2]
    return points, leftmost_id, rightmost_id


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


def vtp_to_poly_string(
    points: Sequence[Point2D],
    edges: Sequence[Edge],
    holes: Sequence[Point2D] | None = None,
    attributes: Sequence[Point2D] | None = None,
) -> str:
    """Convert points and edges to a Triangle POLY format string.

    Args:
        points: List of (x, y) coordinates.
        edges: List of edge tuples (i, j).
        holes: Optional list of hole points.
        attributes: Optional list of region attributes.

    Returns:
        The POLY format string.
    """
    holes = holes or []
    attributes = attributes or []
    lines = []

    # Section: Header with points
    lines.append(f"{len(points)} 2 {len(attributes)} 0")
    for i, point in enumerate(points):
        lines.append(f"{i + 1} {point.x} {point.y}")

    # Segments
    lines.append(f"{len(edges)} 0")
    for i, edge in enumerate(edges):
        lines.append(f"{i + 1} {edge.start + 1} {edge.end + 1}")  # convert to 1-based

    # Holes
    lines.append(f"{len(holes)}")
    for i, point in enumerate(holes):
        lines.append(f"{i + 1} {point.x} {point.y}")

    # Regions
    lines.append(f"{len(attributes)}")
    for i, point in enumerate(attributes):
        lines.append(f"{i + 1} {point.x} {point.y} {i + 1} -1")

    return "\n".join(lines)


def to_off_string(points: Sequence[Point2D], faces: Sequence[Face]) -> str:
    """Convert points and faces to an OFF (Object File Format) string.

    Args:
        points: List of (x, y) coordinates (2D, z will be 0).
        faces: List of faces, each face is a list of vertex indices (0-based).

    Returns:
        The OFF format string.
    """
    lines = ["OFF"]

    num_vertices = len(points)
    num_faces = len(faces)
    num_edges = 0  # can be 0 if we don't want to count

    lines.append(f"{num_vertices} {num_faces} {num_edges}")

    # Write vertices with z = 0
    for point in points:
        lines.append(f"{point.x} {point.y} 0")

    # Faces
    for face in faces:
        k = len(face.vertices)
        indices = " ".join(str(idx) for idx in face.vertices)
        lines.append(f"{k} {indices}")

    return "\n".join(lines)


def write_vtp(
    filename: str | Path,
    points: Sequence[Point2D],
    cells: Sequence[Face],
) -> None:
    """Write points and cells to a VTP (VTK PolyData) file.

    Args:
        filename: Path to the output VTP file.
        points: List of (x, y) coordinates.
        cells: List of cell tuples. For edges: (i, j), for triangles: (i, j, k).
    """
    import vtk

    # Create VTK points (3D with z=0)
    vtk_points = vtk.vtkPoints()
    for point in points:
        vtk_points.InsertNextPoint(point.x, point.y, 0.0)

    # Determine cell type based on first cell
    if not cells:
        # Empty mesh
        polydata = vtk.vtkPolyData()
        polydata.SetPoints(vtk_points)
    elif len(cells[0].vertices) == 2:
        # Edges (lines)
        lines = vtk.vtkCellArray()
        for cell in cells:
            i, j = cell.vertices
            line = vtk.vtkLine()
            line.GetPointIds().SetId(0, i)
            line.GetPointIds().SetId(1, j)
            lines.InsertNextCell(line)
        polydata = vtk.vtkPolyData()
        polydata.SetPoints(vtk_points)
        polydata.SetLines(lines)
    else:
        # Triangles or polygons
        polys = vtk.vtkCellArray()
        for cell in cells:
            polygon = vtk.vtkPolygon()
            polygon.GetPointIds().SetNumberOfIds(len(cell.vertices))
            for idx, vertex_id in enumerate(cell.vertices):
                polygon.GetPointIds().SetId(idx, vertex_id)
            polys.InsertNextCell(polygon)
        polydata = vtk.vtkPolyData()
        polydata.SetPoints(vtk_points)
        polydata.SetPolys(polys)

    # Write to file
    writer = vtk.vtkXMLPolyDataWriter()
    writer.SetFileName(str(filename))
    writer.SetInputData(polydata)
    writer.Write()


def read_triangle_mesh(
    basename: str | Path,
) -> tuple[list[Point2D], list[Face], list[int]]:
    """Read Triangle mesh output files (.1.node and .1.ele).

    Args:
        basename: Path without extension (e.g., '/tmp/mesh' reads '/tmp/mesh.1.node')

    Returns:
        Tuple of (points, triangles, attributes) where:
        - points are (x, y) coordinates
        - triangles are (i, j, k) vertex indices (0-based)
        - attributes are integer region attributes per triangle (empty if none)
    """
    basename = Path(basename)
    node_file = basename.parent / f"{basename.name}.1.node"
    ele_file = basename.parent / f"{basename.name}.1.ele"

    # Read node file
    points: list[Point2D] = []
    with node_file.open() as f:
        # First line: <# of vertices> <dimension> <# of attributes> <boundary markers>
        header = f.readline().split()
        num_points = int(header[0])

        for _ in range(num_points):
            parts = f.readline().split()
            # Format: <vertex #> <x> <y> [attributes] [boundary marker]
            x, y = float(parts[1]), float(parts[2])
            points.append(Point2D(x, y))

    # Read element file
    triangles: list[Face] = []
    attributes: list[int] = []
    with ele_file.open() as f:
        # First line: <# of triangles> <nodes per triangle> <# of attributes>
        header = f.readline().split()
        num_triangles = int(header[0])
        num_attributes = int(header[2]) if len(header) > 2 else 0

        for _ in range(num_triangles):
            parts = f.readline().split()
            # Format: <triangle #> <node 1> <node 2> <node 3> [attributes]
            # Triangle uses 1-based indexing, convert to 0-based
            i, j, k = int(parts[1]) - 1, int(parts[2]) - 1, int(parts[3]) - 1
            triangles.append(Face((i, j, k)))

            # Read attribute if present
            if num_attributes > 0 and len(parts) > 4:
                attr = int(parts[4])
                attributes.append(attr)

    return points, triangles, attributes


def write_vtu(
    filename: str | Path,
    points: Sequence[Point2D],
    triangles: Sequence[Face],
    attributes: Sequence[int] | None = None,
) -> None:
    """Write a 2D triangle mesh to a VTU (VTK UnstructuredGrid) file.

    Args:
        filename: Path to the output VTU file.
        points: List of (x, y) coordinates.
        triangles: List of triangle tuples (i, j, k) with 0-based vertex indices.
        attributes: Optional list of integer material attributes per triangle.
    """
    filename = Path(filename)

    # Create VTK points (3D with z=0)
    vtk_points = vtk.vtkPoints()
    for point in points:
        vtk_points.InsertNextPoint(point.x, point.y, 0.0)

    # Create cell array for triangles
    cells = vtk.vtkCellArray()
    for triangle_indices in triangles:
        i, j, k = triangle_indices.vertices
        triangle = vtk.vtkTriangle()
        triangle.GetPointIds().SetId(0, i)
        triangle.GetPointIds().SetId(1, j)
        triangle.GetPointIds().SetId(2, k)
        cells.InsertNextCell(triangle)

    # Create unstructured grid
    grid = vtk.vtkUnstructuredGrid()
    grid.SetPoints(vtk_points)
    grid.SetCells(vtk.VTK_TRIANGLE, cells)

    # Add material attributes as cell data if provided
    if attributes is not None and len(attributes) > 0:
        vtk_attrs = vtk.vtkIntArray()
        vtk_attrs.SetName("Material")
        for attr in attributes:
            vtk_attrs.InsertNextValue(attr)
        grid.GetCellData().SetScalars(vtk_attrs)

    # Write to file
    writer = vtk.vtkXMLUnstructuredGridWriter()
    writer.SetFileName(str(filename))
    writer.SetInputData(grid)
    writer.Write()
