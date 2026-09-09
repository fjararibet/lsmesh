"""Typed geometry primitives used by the meshing pipeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Point2D:
    """A 2D point with named coordinates."""

    x: float
    y: float

    def __lt__(self, other: Point2D) -> bool:
        return self.as_tuple() < other.as_tuple()

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass(frozen=True)
class Point3D:
    """A 3D point with named coordinates."""

    x: float
    y: float
    z: float

    def __lt__(self, other: Point3D) -> bool:
        return self.as_tuple() < other.as_tuple()

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class Region3D:
    """An interior sample point that tags one material volume."""

    point: Point3D
    material: int


@dataclass(frozen=True)
class Edge:
    """An edge connecting two point indices."""

    start: int
    end: int

    def as_tuple(self) -> tuple[int, int]:
        return (self.start, self.end)

    def sorted(self) -> Edge:
        return Edge(min(self.start, self.end), max(self.start, self.end))


@dataclass(frozen=True)
class Face:
    """A polygonal face defined by point indices."""

    vertices: tuple[int, ...]

    def as_tuple(self) -> tuple[int, ...]:
        return self.vertices

    def as_list(self) -> list[int]:
        return list(self.vertices)
