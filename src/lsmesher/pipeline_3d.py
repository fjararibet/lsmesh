"""Composable 3D mesh pipeline functions."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import pairwise, product
from typing import TYPE_CHECKING, Protocol

import numpy as np

from lsmesher.geometry_types import Face, Point3D, Region3D
from lsmesher.pipeline_types import Surface3D
from lsmesher.polygon_io_3d import (
    read_vtp_faces,
    read_vtp_points,
    to_off_string,
    vtp_to_poly_string,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

COORDINATE_PRECISION = 9
BOTTOM_MARGIN = 0.10
SIDE_WALL_TOLERANCE_FACTOR = 5e-4
SEAM_PROTECTION_RINGS = 8
DEFAULT_TARGET_TOTAL_FACES = 5_600
CoordinateKey = tuple[float, float, float]
EdgeKey = tuple[CoordinateKey, CoordinateKey]


@dataclass(frozen=True)
class DecimationOptions3D:
    """Tunable parameters for 3D patch decimation.

    With ``preserve_boundary`` (the default) patch boundaries stay exactly
    fixed, so decimated surfaces keep conforming where they meet and
    ``boundary_weight`` has no effect. Disabling it lets boundaries move and
    makes ``boundary_weight`` meaningful, but usually breaks layer
    conformity — expect holes at material interfaces and failures when
    closing or tetrahedralizing the merged surface.
    """

    enabled: bool = True
    target_total_faces: int | None = None
    target_edge_length: float | None = None
    target_faces: int | None = None
    quality_threshold: float = 0.3
    preserve_boundary: bool = True
    boundary_weight: float = 1000.0
    optimal_placement: bool = False
    planar_quadric: bool = True
    planar_weight: float = 0.001


@dataclass(frozen=True)
class DecimationReport:
    """Requested and achieved size of the unique conforming patch complex."""

    mode: str
    requested_faces: int
    original_faces: int
    achieved_faces: int
    protected_faces: int
    boundary_limited_faces: int


class SurfaceDecimator3D(Protocol):
    """Callable interface for 3D surface decimation."""

    def __call__(self, surface: Surface3D) -> Surface3D:
        """Return a decimated 3D surface."""
        ...


def read_3d_surfaces(files: Sequence[str | Path]) -> tuple[Surface3D, ...]:
    """Read VTP files into 3D pipeline surfaces."""
    return tuple(
        Surface3D(
            points=tuple(read_vtp_points(file)),
            faces=tuple(read_vtp_faces(file)),
        )
        for file in files
    )


def compute_bottom_points_3d_from_surfaces(
    surfaces: Sequence[Surface3D],
    *,
    bottom_margin: float = BOTTOM_MARGIN,
) -> tuple[Point3D, Point3D, Point3D, Point3D]:
    """Compute bottom corner points from all input surfaces."""
    all_points = tuple(point for surface in surfaces for point in surface.points)
    if not all_points:
        msg = "Cannot compute bottom points: no input points."
        raise ValueError(msg)

    z_coords = [point.z for point in all_points]
    min_z_raw = min(z_coords)
    max_z = max(z_coords)
    height = max_z - min_z_raw

    if height == 0:
        msg = (
            "Cannot compute bottom points: all input points have the same Z "
            f"coordinate ({min_z_raw}). The geometry has zero height."
        )
        raise ValueError(msg)

    min_x = min(point.x for point in all_points)
    max_x = max(point.x for point in all_points)
    min_y = min(point.y for point in all_points)
    max_y = max(point.y for point in all_points)
    min_z = min_z_raw - height * bottom_margin

    return (
        Point3D(min_x, max_y, min_z),
        Point3D(max_x, max_y, min_z),
        Point3D(min_x, min_y, min_z),
        Point3D(max_x, min_y, min_z),
    )


def _offset_face(face: Face, offset: int) -> Face:
    return Face(tuple(vertex + offset for vertex in face.vertices))


def _point_key(point: Point3D, precision: int = COORDINATE_PRECISION) -> CoordinateKey:
    return (
        round(point.x, precision),
        round(point.y, precision),
        round(point.z, precision),
    )


def _edge_key(first: CoordinateKey, second: CoordinateKey) -> EdgeKey:
    return (first, second) if first <= second else (second, first)


def _face_key(surface: Surface3D, face: Face) -> tuple[tuple[float, float, float], ...]:
    return tuple(sorted(_point_key(surface.points[vertex]) for vertex in face.vertices))


def _edge_counts(surface: Surface3D) -> dict[tuple[int, int], int]:
    edge_counts: dict[tuple[int, int], int] = defaultdict(int)
    for face in surface.faces:
        if len(face.vertices) < 3:
            continue
        for start, end in zip(
            face.vertices,
            (*face.vertices[1:], face.vertices[0]),
            strict=True,
        ):
            edge_counts[tuple(sorted((start, end)))] += 1
    return edge_counts


def _boundary_edges(surface: Surface3D) -> tuple[tuple[int, int], ...]:
    return tuple(edge for edge, count in _edge_counts(surface).items() if count == 1)


def _has_fold_edges(surface: Surface3D) -> bool:
    """Return True if any edge has an odd face count above one.

    Edges used once are surface boundary and edges used an even number of
    times are interior (counts above two occur where sheets of a pinched-off
    surface touch). An odd count above one marks a fold-over flap that opens
    a hole once duplicate faces are merged away.
    """
    return any(count > 1 and count % 2 == 1 for count in _edge_counts(surface).values())


def _deduplicate_surface(
    surface: Surface3D, *, precision: int = COORDINATE_PRECISION
) -> Surface3D:
    points: list[Point3D] = []
    point_indices: dict[tuple[float, float, float], int] = {}
    remap: dict[int, int] = {}
    for index, point in enumerate(surface.points):
        key = _point_key(point, precision)
        if key not in point_indices:
            point_indices[key] = len(points)
            points.append(point)
        remap[index] = point_indices[key]

    faces: list[Face] = []
    seen_faces: set[tuple[int, ...]] = set()
    for face in surface.faces:
        vertices = tuple(remap[vertex] for vertex in face.vertices)
        if len(set(vertices)) < 3:
            continue
        key = tuple(sorted(vertices))
        if key in seen_faces:
            continue
        seen_faces.add(key)
        faces.append(Face(vertices))

    return Surface3D(points=tuple(points), faces=tuple(faces))


def _face_edges(surface: Surface3D, face: Face) -> list[EdgeKey]:
    """Return a face's edges as sorted coordinate-key pairs."""
    vertices = face.vertices
    return [
        _edge_key(
            _point_key(surface.points[start]),
            _point_key(surface.points[end]),
        )
        for start, end in zip(vertices, (*vertices[1:], vertices[0]), strict=True)
    ]


def _boundary_edge_keys(
    surface: Surface3D,
) -> set[EdgeKey]:
    return {
        _edge_key(
            _point_key(surface.points[start]),
            _point_key(surface.points[end]),
        )
        for start, end in _boundary_edges(surface)
    }


def _triangulate_faces(surface: Surface3D) -> Surface3D:
    """Fan-triangulate polygonal faces, keeping boundary edges unchanged."""
    if all(len(face.vertices) == 3 for face in surface.faces):
        return surface
    triangles: list[Face] = []
    for face in surface.faces:
        vertices = face.vertices
        if len(vertices) < 3:
            continue
        triangles.extend(
            Face((vertices[0], vertices[index], vertices[index + 1]))
            for index in range(1, len(vertices) - 1)
        )
    return Surface3D(points=surface.points, faces=tuple(triangles))


def _decimate_patch_once(
    patch: Surface3D,
    target_face_count: int,
    options: DecimationOptions3D,
) -> Surface3D:
    # Imported lazily: pymeshlab initializes a bundled Qt runtime whose
    # thread-bound state corrupts the heap when loaded into short-lived
    # threads (e.g. Streamlit script runs). Keeping the import out of module
    # scope lets the viewer process avoid loading it at all.
    import pymeshlab as ml  # noqa: PLC0415

    points_arr = np.array([point.as_tuple() for point in patch.points])
    faces_arr = np.array([face.as_tuple() for face in patch.faces])
    mesh = ml.Mesh(vertex_matrix=points_arr, face_matrix=faces_arr)  # type: ignore[attr-defined]
    mesh_set = ml.MeshSet()  # type: ignore[attr-defined]
    mesh_set.add_mesh(mesh, "patch")
    mesh_set.meshing_decimation_quadric_edge_collapse(
        targetfacenum=target_face_count,
        qualitythr=options.quality_threshold,
        preserveboundary=options.preserve_boundary,
        boundaryweight=options.boundary_weight,
        preservenormal=True,
        preservetopology=True,
        optimalplacement=options.optimal_placement,
        planarquadric=options.planar_quadric,
        planarweight=options.planar_weight,
    )
    result = mesh_set.current_mesh()

    return Surface3D(
        points=tuple(
            Point3D(float(x), float(y), float(z)) for x, y, z in result.vertex_matrix()
        ),
        faces=tuple(
            Face(tuple(int(vertex) for vertex in face)) for face in result.face_matrix()
        ),
    )


def decimate_3d_patch(
    patch: Surface3D,
    options: DecimationOptions3D | None = None,
    *,
    target_faces: int | None = None,
) -> Surface3D:
    """Decimate one manifold patch while keeping its boundary exactly fixed.

    With ``preserve_boundary`` the patch boundary must survive unchanged so
    adjacent patches still conform after decimation; without it the boundary
    may move and conformity is the caller's problem. Either way the
    decimated patch must stay free of fold-over flaps once coincident points
    and duplicate faces are merged, or the discarded duplicates would open
    holes when the surfaces are merged downstream. If PyMeshLab violates an
    invariant at the requested target, the target is relaxed; the original
    patch is returned when no valid decimation is found.
    """
    options = options or DecimationOptions3D()
    triangulated = _triangulate_faces(patch)
    target_faces = target_faces or _single_patch_target(triangulated, options)
    if len(triangulated.faces) <= target_faces:
        return patch

    boundary = _boundary_edge_keys(patch)
    target = target_faces
    if options.preserve_boundary:
        # A patch that keeps its boundary cannot drop below the face count
        # the boundary edges themselves require.
        target = max(target, len(boundary))
    while target < len(triangulated.faces):
        decimated = _deduplicate_surface(
            _decimate_patch_once(triangulated, target, options)
        )
        boundary_ok = (
            not options.preserve_boundary or _boundary_edge_keys(decimated) == boundary
        )
        if decimated.faces and boundary_ok and not _has_fold_edges(decimated):
            return decimated
        target *= 2
    return patch


def _surface_area(surface: Surface3D) -> float:
    area = 0.0
    for face in surface.faces:
        if len(face.vertices) < 3:
            continue
        origin = np.array(surface.points[face.vertices[0]].as_tuple())
        for index in range(1, len(face.vertices) - 1):
            first = np.array(surface.points[face.vertices[index]].as_tuple()) - origin
            second = (
                np.array(surface.points[face.vertices[index + 1]].as_tuple()) - origin
            )
            area += float(np.linalg.norm(np.cross(first, second))) * 0.5
    return area


def _single_patch_target(patch: Surface3D, options: DecimationOptions3D) -> int:
    if options.target_edge_length is not None:
        face_area = np.sqrt(3.0) * options.target_edge_length**2 / 4.0
        return max(1, int(np.ceil(_surface_area(patch) / face_area)))
    if options.target_faces is not None:
        return options.target_faces
    return options.target_total_faces or DEFAULT_TARGET_TOTAL_FACES


class _SurfaceBuilder:
    """Accumulates coordinate-keyed faces into a compact surface."""

    def __init__(self) -> None:
        self._points: list[Point3D] = []
        self._point_index: dict[tuple, int] = {}
        self._faces: list[Face] = []

    def add_faces(self, surface: Surface3D, faces: Sequence[Face]) -> None:
        for face in faces:
            vertices = []
            for vertex in face.vertices:
                point = surface.points[vertex]
                point_key = _point_key(point)
                if point_key not in self._point_index:
                    self._point_index[point_key] = len(self._points)
                    self._points.append(point)
                vertices.append(self._point_index[point_key])
            self._faces.append(Face(tuple(vertices)))

    def build(self) -> Surface3D:
        return Surface3D(points=tuple(self._points), faces=tuple(self._faces))


def _patch_groups(
    surfaces: Sequence[Surface3D],
) -> list[tuple[frozenset[int], Surface3D]]:
    """Partition faces into edge-connected patches with equal owner sets."""
    owner_sets: dict[tuple, set[int]] = defaultdict(set)
    representative: dict[tuple, tuple[int, Face]] = {}
    for index, surface in enumerate(surfaces):
        for face in surface.faces:
            key = _face_key(surface, face)
            owner_sets[key].add(index)
            representative.setdefault(key, (index, face))
    owners = {key: frozenset(value) for key, value in owner_sets.items()}

    key_edges: dict[tuple, list[tuple]] = {}
    edge_to_keys: dict[tuple, list[tuple]] = defaultdict(list)
    for key, (index, face) in representative.items():
        edges = _face_edges(surfaces[index], face)
        key_edges[key] = edges
        for edge in edges:
            edge_to_keys[edge].append(key)

    unvisited = set(representative)
    groups: list[tuple[frozenset[int], Surface3D]] = []
    while unvisited:
        seed = unvisited.pop()
        label = owners[seed]
        group = _connected_keys(seed, label, owners, key_edges, edge_to_keys, unvisited)

        builder = _SurfaceBuilder()
        for key in group:
            index, face = representative[key]
            builder.add_faces(surfaces[index], (face,))
        groups.append((label, builder.build()))
    return groups


def _connected_keys(  # noqa: PLR0913
    seed: tuple,
    label: frozenset[int],
    owners: dict[tuple, frozenset[int]],
    key_edges: dict[tuple, list[tuple]],
    edge_to_keys: dict[tuple, list[tuple]],
    unvisited: set[tuple],
) -> list[tuple]:
    """Collect all unvisited same-label face keys edge-connected to seed."""
    group = [seed]
    stack = [seed]
    while stack:
        current = stack.pop()
        for edge in key_edges[current]:
            for neighbor in edge_to_keys[edge]:
                if neighbor in unvisited and owners[neighbor] == label:
                    unvisited.discard(neighbor)
                    group.append(neighbor)
                    stack.append(neighbor)
    return group


def _seam_vertices(surface: Surface3D) -> set[int]:
    """Return vertices where the surface touches itself.

    Covers endpoints of edges shared by more than two faces (pinch-off
    seams) and vertices whose incident faces do not form a single
    edge-connected fan (isolated touch points).
    """
    seam = {
        vertex
        for edge, count in _edge_counts(surface).items()
        if count > 2
        for vertex in edge
    }
    vertex_faces: dict[int, list[int]] = defaultdict(list)
    for index, face in enumerate(surface.faces):
        if len(face.vertices) < 3:
            continue
        for vertex in set(face.vertices):
            vertex_faces[vertex].append(index)
    for vertex, incident in vertex_faces.items():
        if vertex not in seam and not _is_single_fan(surface, vertex, incident):
            seam.add(vertex)
    return seam


def _is_single_fan(surface: Surface3D, vertex: int, incident: Sequence[int]) -> bool:
    """Return True if the faces incident to vertex are edge-connected."""
    edge_faces: dict[tuple[int, int], list[int]] = defaultdict(list)
    for face_index in incident:
        vertices = surface.faces[face_index].vertices
        for start, end in zip(vertices, (*vertices[1:], vertices[0]), strict=True):
            if vertex in (start, end):
                edge_faces[tuple(sorted((start, end)))].append(face_index)
    seen = {incident[0]}
    stack = [incident[0]]
    while stack:
        current = stack.pop()
        vertices = surface.faces[current].vertices
        for start, end in zip(vertices, (*vertices[1:], vertices[0]), strict=True):
            if vertex not in (start, end):
                continue
            for neighbor in edge_faces[tuple(sorted((start, end)))]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
    return len(seen) == len(incident)


def _split_seam_neighborhood(
    patch: Surface3D, rings: int = SEAM_PROTECTION_RINGS
) -> tuple[Surface3D | None, Surface3D | None]:
    """Split a patch into a protected seam neighborhood and the remainder.

    Around self-touching seams the surface sheets are nearly tangent, so
    decimating there easily pushes one sheet through the other. Faces within
    ``rings`` vertex rings of a seam keep their original triangulation; only
    the remainder is decimated, with the cut curve pinned as part of its
    boundary.
    """
    seam = _seam_vertices(patch)
    if not seam:
        return None, patch

    vertex_faces: dict[int, list[int]] = defaultdict(list)
    for index, face in enumerate(patch.faces):
        for vertex in set(face.vertices):
            vertex_faces[vertex].append(index)

    protected: set[int] = set()
    frontier = set(seam)
    for _ in range(rings):
        added = {
            index for vertex in frontier for index in vertex_faces[vertex]
        } - protected
        if not added:
            break
        protected |= added
        frontier = {vertex for index in added for vertex in patch.faces[index].vertices}

    def _sub_surface(indices: Sequence[int]) -> Surface3D | None:
        if not indices:
            return None
        builder = _SurfaceBuilder()
        builder.add_faces(patch, [patch.faces[index] for index in indices])
        return builder.build()

    remainder = [index for index in range(len(patch.faces)) if index not in protected]
    return _sub_surface(sorted(protected)), _sub_surface(remainder)


@dataclass(frozen=True)
class _PatchWork:
    owners: frozenset[int]
    protected: Surface3D | None
    remainder: Surface3D | None


def _area_weighted_targets(
    patches: Sequence[Surface3D], total_faces: int
) -> tuple[int, ...]:
    """Allocate a global budget by true 3D area, capped by input face counts."""
    if not patches:
        return ()
    capacities = [len(_triangulate_faces(patch).faces) for patch in patches]
    budget = max(1, min(total_faces, sum(capacities)))
    areas = [_surface_area(patch) for patch in patches]
    total_area = sum(areas)
    weights = areas if total_area > 0 else [1.0] * len(patches)
    weight_sum = sum(weights)
    quotas = [budget * weight / weight_sum for weight in weights]
    targets = [
        min(capacity, max(1, int(quota)))
        for quota, capacity in zip(quotas, capacities, strict=True)
    ]

    remaining = budget - sum(targets)
    order = sorted(
        range(len(patches)),
        key=lambda index: (quotas[index] - int(quotas[index]), areas[index]),
        reverse=True,
    )
    while remaining > 0:
        changed = False
        for index in order:
            if targets[index] >= capacities[index]:
                continue
            targets[index] += 1
            remaining -= 1
            changed = True
            if remaining == 0:
                break
        if not changed:
            break
    return tuple(targets)


def _decimation_targets(
    patches: Sequence[Surface3D], options: DecimationOptions3D
) -> tuple[str, int, tuple[int, ...]]:
    if options.target_edge_length is not None:
        targets = tuple(_single_patch_target(patch, options) for patch in patches)
        return "edge_length", sum(targets), targets
    if options.target_faces is not None:
        targets = tuple(options.target_faces for _ in patches)
        return "legacy_per_patch", sum(targets), targets
    requested = options.target_total_faces or DEFAULT_TARGET_TOTAL_FACES
    return "total_faces", requested, _area_weighted_targets(patches, requested)


def decimate_conforming_3d_surfaces(
    surfaces: Sequence[Surface3D],
    *,
    decimator: SurfaceDecimator3D | None = None,
    seam_protection_rings: int = SEAM_PROTECTION_RINGS,
) -> tuple[Surface3D, ...]:
    """Decimate conforming surfaces patch-wise so shared regions stay identical.

    The surfaces are partitioned into patches: maximal edge-connected groups
    of faces owned by the same set of surfaces. Each patch is decimated once
    with its boundary kept fixed and every surface is rebuilt from its
    patches, so coincident regions remain bitwise identical and the
    material-junction curves survive decimation unchanged. Faces near
    self-touching seams are excluded from decimation so nearly tangent
    sheets keep their exact, conforming triangulation.
    """
    surfaces, _ = decimate_conforming_3d_surfaces_with_report(
        surfaces,
        decimator=decimator,
        seam_protection_rings=seam_protection_rings,
    )
    return surfaces


def decimate_conforming_3d_surfaces_with_report(
    surfaces: Sequence[Surface3D],
    *,
    options: DecimationOptions3D | None = None,
    decimator: SurfaceDecimator3D | None = None,
    seam_protection_rings: int = SEAM_PROTECTION_RINGS,
) -> tuple[tuple[Surface3D, ...], DecimationReport]:
    """Decimate conforming patches and report the effective global budget."""
    options = options or DecimationOptions3D()
    builders = [_SurfaceBuilder() for _ in surfaces]
    work: list[_PatchWork] = []
    original_faces = 0
    for label, patch in _patch_groups(surfaces):
        original_faces += len(_triangulate_faces(patch).faces)
        protected, remainder = _split_seam_neighborhood(
            patch, rings=seam_protection_rings
        )
        work.append(_PatchWork(label, protected, remainder))

    remainders = tuple(item.remainder for item in work if item.remainder is not None)
    mode, requested, targets = _decimation_targets(remainders, options)
    target_iterator = iter(targets)
    protected_faces = 0
    boundary_limited_faces = 0
    achieved_faces = 0
    for item in work:
        target = next(target_iterator) if item.remainder is not None else None
        if item.remainder is None:
            decimated = None
        elif decimator is not None:
            decimated = decimator(item.remainder)
        else:
            decimated = decimate_3d_patch(
                item.remainder,
                options,
                target_faces=target,
            )
        if item.protected is not None:
            protected_faces += len(item.protected.faces)
        if decimated is not None and target is not None:
            boundary_limited_faces += max(0, len(decimated.faces) - target)
        achieved_faces += sum(
            len(piece.faces)
            for piece in (item.protected, decimated)
            if piece is not None
        )
        for piece in (item.protected, decimated):
            if piece is None:
                continue
            for index in item.owners:
                builders[index].add_faces(piece, piece.faces)
    report = DecimationReport(
        mode=mode,
        requested_faces=requested,
        original_faces=original_faces,
        achieved_faces=achieved_faces,
        protected_faces=protected_faces,
        boundary_limited_faces=boundary_limited_faces,
    )
    return tuple(builder.build() for builder in builders), report


def _fan_triangles(surface: Surface3D) -> np.ndarray:
    """Return all faces fan-triangulated as an (n, 3, 3) coordinate array."""
    triangles: list[list[tuple[float, float, float]]] = []
    for face in surface.faces:
        vertices = face.vertices
        if len(vertices) < 3:
            continue
        first = surface.points[vertices[0]].as_tuple()
        triangles.extend(
            [
                first,
                surface.points[vertices[index]].as_tuple(),
                surface.points[vertices[index + 1]].as_tuple(),
            ]
            for index in range(1, len(vertices) - 1)
        )
    if not triangles:
        return np.zeros((0, 3, 3))
    return np.array(triangles)


def _vertical_hits(triangles: np.ndarray, x: float, y: float) -> tuple[float, ...]:
    """Return z values where the vertical line at (x, y) crosses the triangles."""
    if not len(triangles):
        return ()

    a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]

    def edge_weight(start: np.ndarray, end: np.ndarray) -> np.ndarray:
        return (end[:, 0] - start[:, 0]) * (y - start[:, 1]) - (
            end[:, 1] - start[:, 1]
        ) * (x - start[:, 0])

    weight_a = edge_weight(b, c)
    weight_b = edge_weight(c, a)
    weight_c = edge_weight(a, b)
    doubled_area = weight_a + weight_b + weight_c
    epsilon = 1e-9 * np.abs(doubled_area)
    sign = np.sign(doubled_area)
    inside = (
        (np.abs(doubled_area) > 1e-30)
        & (sign * weight_a >= -epsilon)
        & (sign * weight_b >= -epsilon)
        & (sign * weight_c >= -epsilon)
    )
    if not inside.any():
        return ()

    z_values = (
        weight_a[inside] * a[inside, 2]
        + weight_b[inside] * b[inside, 2]
        + weight_c[inside] * c[inside, 2]
    ) / doubled_area[inside]
    return tuple(float(value) for value in z_values)


def _unique_faces(surface: Surface3D, lower: Surface3D | None) -> list[Face]:
    """Return faces of surface that are not coincident with faces of lower."""
    if lower is None:
        return list(surface.faces)
    lower_keys = {_face_key(lower, face) for face in lower.faces}
    return [
        face for face in surface.faces if _face_key(surface, face) not in lower_keys
    ]


def _face_components(faces: Sequence[Face]) -> list[list[Face]]:
    """Group faces into edge-connected components."""
    edge_to_faces: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, face in enumerate(faces):
        vertices = face.vertices
        for start, end in zip(vertices, (*vertices[1:], vertices[0]), strict=True):
            edge_to_faces[tuple(sorted((start, end)))].append(index)

    components: list[list[Face]] = []
    unvisited = set(range(len(faces)))
    while unvisited:
        stack = [unvisited.pop()]
        component = [stack[0]]
        while stack:
            current = stack.pop()
            vertices = faces[current].vertices
            for start, end in zip(vertices, (*vertices[1:], vertices[0]), strict=True):
                for neighbor in edge_to_faces[tuple(sorted((start, end)))]:
                    if neighbor in unvisited:
                        unvisited.discard(neighbor)
                        component.append(neighbor)
                        stack.append(neighbor)
        components.append([faces[index] for index in component])
    return components


def _face_centroid(surface: Surface3D, face: Face) -> Point3D:
    count = len(face.vertices)
    return Point3D(
        sum(surface.points[vertex].x for vertex in face.vertices) / count,
        sum(surface.points[vertex].y for vertex in face.vertices) / count,
        sum(surface.points[vertex].z for vertex in face.vertices) / count,
    )


def _projected_area(surface: Surface3D, face: Face) -> float:
    """Return the absolute XY-projected area of a face."""
    area = 0.0
    vertices = face.vertices
    for start, end in zip(vertices, (*vertices[1:], vertices[0]), strict=True):
        first = surface.points[start]
        second = surface.points[end]
        area += first.x * second.y - second.x * first.y
    return abs(area) / 2


def _component_region_point(
    component: Sequence[Face],
    surface: Surface3D,
    hit_triangles: np.ndarray,
    floor_z: float,
    *,
    min_gap: float,
) -> Point3D:
    """Sample an interior point below one component of unique faces.

    Casts a vertical ray down from a face centroid and takes the midpoint to
    the nearest surface crossing below it, so the sample stays strictly inside
    the material volume capped by the component.
    """
    candidates = sorted(
        component,
        key=lambda face: _projected_area(surface, face),
        reverse=True,
    )
    tolerance = min_gap * 1e-6
    best: tuple[float, float, float, float] | None = None
    for face in candidates:
        centroid = _face_centroid(surface, face)
        hits = [
            z
            for z in _vertical_hits(hit_triangles, centroid.x, centroid.y)
            if z < centroid.z - tolerance
        ]
        z_low = max(hits, default=floor_z)
        gap = centroid.z - z_low
        if best is None or gap > best[0]:
            best = (gap, centroid.x, centroid.y, (centroid.z + z_low) / 2)
        if best[0] >= min_gap:
            break

    if best is None:
        msg = "Cannot sample region point: component has no faces."
        raise ValueError(msg)
    return Point3D(best[1], best[2], best[3])


def collect_3d_regions(
    surfaces: Sequence[Surface3D],
    *,
    bottom_margin: float = BOTTOM_MARGIN,
) -> tuple[Region3D, ...]:
    """Sample one interior region point per material volume component.

    Surfaces must be sorted bottom-up. Layer ``i`` is the material between
    surface ``i - 1`` (or the closure bottom plane for the first layer) and
    surface ``i``; each edge-connected component of the faces unique to
    surface ``i`` caps one volume component and receives material ID ``i + 1``.
    """
    all_z = [point.z for surface in surfaces for point in surface.points]
    min_z, max_z = min(all_z), max(all_z)
    height = max_z - min_z
    floor_z = min_z - height * bottom_margin
    min_gap = height * 0.05

    triangles = [_fan_triangles(surface) for surface in surfaces]
    regions: list[Region3D] = []
    for index, surface in enumerate(surfaces):
        lower = surfaces[index - 1] if index else None
        hit_triangles = (
            np.concatenate((triangles[index], triangles[index - 1]))
            if index
            else triangles[index]
        )
        for component in _face_components(_unique_faces(surface, lower)):
            point = _component_region_point(
                component,
                surface,
                hit_triangles,
                floor_z,
                min_gap=min_gap,
            )
            regions.append(Region3D(point=point, material=index + 1))
    return tuple(regions)


def merge_3d_surfaces(
    surfaces: Sequence[Surface3D],
    *,
    bottom_margin: float = BOTTOM_MARGIN,
) -> Surface3D:
    """Merge conforming surfaces into one complex with material region points.

    Input surfaces must conform exactly where they coincide (identical
    vertices and faces), as produced by extracting wrapped level sets from a
    shared grid. Coincident points and duplicate faces are merged so shared
    interface faces appear exactly once.
    """
    if not surfaces:
        msg = "Cannot merge 3D surfaces: no surfaces."
        raise ValueError(msg)
    if any(not surface.points for surface in surfaces):
        msg = "Cannot merge 3D surfaces: all surfaces must have points."
        raise ValueError(msg)

    surfaces = sorted(
        surfaces, key=lambda surface: min(point.z for point in surface.points)
    )
    regions = collect_3d_regions(surfaces, bottom_margin=bottom_margin)

    merged_points: list[Point3D] = []
    merged_faces: list[Face] = []
    for surface in surfaces:
        offset = len(merged_points)
        merged_points.extend(surface.points)
        merged_faces.extend(_offset_face(face, offset) for face in surface.faces)

    merged = _deduplicate_surface(
        Surface3D(points=tuple(merged_points), faces=tuple(merged_faces))
    )
    return Surface3D(
        points=merged.points,
        faces=merged.faces,
        regions=regions,
    )


def close_3d_surface(
    surface: Surface3D,
    *,
    bottom_margin: float = BOTTOM_MARGIN,
) -> Surface3D:
    """Close the open sides of a merged surface with wall and bottom facets.

    All boundary edges of the surface must lie on the four vertical planes of
    its XY bounding box. Each wall becomes one TetGen facet built from the
    boundary edges on that wall, the subdivided vertical corner columns, and a
    bottom edge; a rectangular bottom facet seals the volume from below.
    """
    boundary = _boundary_edges(surface)
    if not boundary:
        return surface

    points = list(surface.points)
    min_x = min(point.x for point in points)
    max_x = max(point.x for point in points)
    min_y = min(point.y for point in points)
    max_y = max(point.y for point in points)
    min_z = min(point.z for point in points)
    max_z = max(point.z for point in points)
    height = max_z - min_z
    if height == 0:
        msg = "Cannot close 3D surface: the geometry has zero height."
        raise ValueError(msg)
    bottom_z = min_z - height * bottom_margin

    walls: dict[str, tuple[str, float]] = {
        "x-": ("x", min_x),
        "x+": ("x", max_x),
        "y-": ("y", min_y),
        "y+": ("y", max_y),
    }
    wall_tolerance = (
        max(max_x - min_x, max_y - min_y, height) * SIDE_WALL_TOLERANCE_FACTOR
    )

    def on_wall(vertex: int, wall: str) -> bool:
        axis, value = walls[wall]
        return abs(getattr(points[vertex], axis) - value) <= wall_tolerance

    wall_edges: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for start, end in boundary:
        matched = [
            wall for wall in walls if on_wall(start, wall) and on_wall(end, wall)
        ]
        if not matched:
            msg = (
                "Cannot close 3D surface: boundary edge "
                f"{points[start]} -> {points[end]} does not lie on a bounding "
                "box side wall."
            )
            raise ValueError(msg)
        for wall in matched:
            wall_edges[wall].append((start, end))

    boundary_vertices = {vertex for edge in boundary for vertex in edge}
    corner_segments: dict[tuple[str, str], list[Face]] = {}
    corner_bottoms: dict[tuple[str, str], int] = {}
    for wall_x, wall_y in product(("x-", "x+"), ("y-", "y+")):
        corner = (wall_x, wall_y)
        column = sorted(
            (
                vertex
                for vertex in boundary_vertices
                if on_wall(vertex, wall_x) and on_wall(vertex, wall_y)
            ),
            key=lambda vertex: points[vertex].z,
        )
        bottom_corner = len(points)
        points.append(Point3D(walls[wall_x][1], walls[wall_y][1], bottom_z))
        corner_bottoms[corner] = bottom_corner
        chain = [bottom_corner, *column]
        corner_segments[corner] = [
            Face((first, second)) for first, second in pairwise(chain)
        ]

    wall_corners: dict[str, tuple[tuple[str, str], tuple[str, str]]] = {
        "x-": (("x-", "y-"), ("x-", "y+")),
        "x+": (("x+", "y-"), ("x+", "y+")),
        "y-": (("x-", "y-"), ("x+", "y-")),
        "y+": (("x-", "y+"), ("x+", "y+")),
    }
    facets: list[tuple[Face, ...]] = []
    for wall, (first_corner, second_corner) in wall_corners.items():
        polygons = [Face(edge) for edge in wall_edges[wall]]
        polygons.extend(corner_segments[first_corner])
        polygons.extend(corner_segments[second_corner])
        polygons.append(
            Face((corner_bottoms[first_corner], corner_bottoms[second_corner]))
        )
        facets.append(tuple(polygons))

    facets.append(
        (
            Face(
                (
                    corner_bottoms[("x-", "y-")],
                    corner_bottoms[("x+", "y-")],
                    corner_bottoms[("x+", "y+")],
                    corner_bottoms[("x-", "y+")],
                )
            ),
        )
    )

    return Surface3D(
        points=tuple(points),
        faces=surface.faces,
        regions=surface.regions,
        facets=(*surface.facets, *facets),
    )


def build_3d_surface(
    surfaces: Sequence[Surface3D],
    *,
    decimation: DecimationOptions3D | None = None,
    decimator: SurfaceDecimator3D | None = None,
    bottom_margin: float = BOTTOM_MARGIN,
    seam_protection_rings: int = SEAM_PROTECTION_RINGS,
) -> Surface3D:
    """Build the final closed 3D surface complex from input surfaces.

    Decimation is controlled by ``decimation`` (defaults to enabled with
    `DecimationOptions3D` defaults). An explicit ``decimator`` overrides the
    options-based patch decimator; passing options with ``enabled=False``
    and no decimator skips decimation entirely.
    """
    surface, _ = build_3d_surface_with_report(
        surfaces,
        decimation=decimation,
        decimator=decimator,
        bottom_margin=bottom_margin,
        seam_protection_rings=seam_protection_rings,
    )
    return surface


def build_3d_surface_with_report(
    surfaces: Sequence[Surface3D],
    *,
    decimation: DecimationOptions3D | None = None,
    decimator: SurfaceDecimator3D | None = None,
    bottom_margin: float = BOTTOM_MARGIN,
    seam_protection_rings: int = SEAM_PROTECTION_RINGS,
) -> tuple[Surface3D, DecimationReport | None]:
    """Build a closed surface and return decimation statistics when enabled."""
    decimation = decimation or DecimationOptions3D()
    report = None
    if decimation.enabled or decimator is not None:
        surfaces, report = decimate_conforming_3d_surfaces_with_report(
            surfaces,
            options=decimation,
            decimator=decimator,
            seam_protection_rings=seam_protection_rings,
        )
    surface = close_3d_surface(
        merge_3d_surfaces(surfaces, bottom_margin=bottom_margin),
        bottom_margin=bottom_margin,
    )
    return surface, report


def surface_3d_to_poly_text(surface: Surface3D) -> str:
    """Serialize a 3D surface to TetGen POLY text."""
    return vtp_to_poly_string(
        points=surface.points,
        faces=surface.faces,
        regions=surface.regions,
        facets=surface.facets,
    )


def surface_3d_to_off_text(surface: Surface3D) -> str:
    """Serialize a 3D surface to OFF text."""
    return to_off_string(points=surface.points, faces=surface.faces)
