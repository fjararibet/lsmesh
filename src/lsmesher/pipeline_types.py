"""Data containers for mesh pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lsmesher.geometry_types import Edge, Face, Point2D, Point3D, Region3D


@dataclass(frozen=True)
class Layer2D:
    """A single 2D input layer made of points and boundary edges."""

    points: tuple[Point2D, ...]
    edges: tuple[Edge, ...]


@dataclass(frozen=True)
class Geometry2D:
    """Merged 2D geometry ready for serialization or meshing."""

    points: tuple[Point2D, ...]
    edges: tuple[Edge, ...]
    attributes: tuple[Point2D, ...] = ()
    attribute_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class Surface3D:
    """A 3D surface complex made of points, faces, and closure facets.

    Faces are ordinary polygons. Each entry in ``facets`` is one TetGen facet
    given as a group of polygons; two-vertex polygons are segments constraining
    the facet's triangulation.
    """

    points: tuple[Point3D, ...]
    faces: tuple[Face, ...]
    regions: tuple[Region3D, ...] = ()
    facets: tuple[tuple[Face, ...], ...] = ()


@dataclass(frozen=True)
class TriangleMesh2D:
    """Triangle mesher output for 2D geometry."""

    points: tuple[Point2D, ...]
    triangles: tuple[Face, ...]
    attributes: tuple[int, ...]
