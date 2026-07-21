"""Geometry checks that run before serialization or external meshing."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal, TypeAlias

from lsmesher.pipeline_types import Geometry2D, Surface3D

Severity: TypeAlias = Literal["warning", "error"]


@dataclass(frozen=True)
class ValidationIssue:
    """One actionable geometry problem."""

    code: str
    message: str
    severity: Severity
    count: int = 1


@dataclass(frozen=True)
class ValidationReport:
    """Collection of geometry issues, separated by severity."""

    issues: tuple[ValidationIssue, ...] = ()

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def raise_for_errors(self) -> None:
        if self.valid:
            return
        from lsmesher.errors import InvalidGeometryError  # noqa: PLC0415

        messages = [issue.message for issue in self.issues if issue.severity == "error"]
        raise InvalidGeometryError("; ".join(messages))


def validate(geometry: Geometry2D | Surface3D) -> ValidationReport:
    """Return structural problems that could make a mesher fail."""
    if isinstance(geometry, Geometry2D):
        return _validate_2d(geometry)
    return _validate_3d(geometry)


def _validate_2d(geometry: Geometry2D) -> ValidationReport:
    issues: list[ValidationIssue] = []
    invalid = sum(
        edge.start < 0
        or edge.end < 0
        or edge.start >= len(geometry.points)
        or edge.end >= len(geometry.points)
        for edge in geometry.edges
    )
    degenerate = sum(edge.start == edge.end for edge in geometry.edges)
    counts = Counter(index for edge in geometry.edges for index in edge.as_tuple())
    open_vertices = sum(count != 2 for count in counts.values())
    if not geometry.points or not geometry.edges:
        issues.append(ValidationIssue("empty", "2D geometry is empty", "error"))
    if invalid:
        issues.append(
            ValidationIssue(
                "invalid-index", "Edges reference missing points", "error", invalid
            )
        )
    if degenerate:
        issues.append(
            ValidationIssue(
                "degenerate-edge",
                "Geometry contains zero-length index edges",
                "error",
                degenerate,
            )
        )
    if open_vertices:
        issues.append(
            ValidationIssue(
                "open-boundary", "2D boundary is not closed", "error", open_vertices
            )
        )
    return ValidationReport(tuple(issues))


def _validate_3d(surface: Surface3D) -> ValidationReport:
    issues: list[ValidationIssue] = []
    invalid = sum(
        vertex < 0 or vertex >= len(surface.points)
        for face in surface.faces
        for vertex in face.vertices
    )
    degenerate = sum(len(set(face.vertices)) < 3 for face in surface.faces)
    face_keys = [tuple(sorted(face.vertices)) for face in surface.faces]
    duplicates = len(face_keys) - len(set(face_keys))
    if not surface.points or not surface.faces:
        issues.append(ValidationIssue("empty", "3D surface is empty", "error"))
    if invalid:
        issues.append(
            ValidationIssue(
                "invalid-index", "Faces reference missing points", "error", invalid
            )
        )
    if degenerate:
        issues.append(
            ValidationIssue(
                "degenerate-face",
                "Surface contains degenerate faces",
                "error",
                degenerate,
            )
        )
    if duplicates:
        issues.append(
            ValidationIssue(
                "duplicate-face",
                "Surface contains duplicate faces",
                "error",
                duplicates,
            )
        )
    if not surface.regions:
        issues.append(
            ValidationIssue(
                "missing-regions", "Surface has no material region points", "warning"
            )
        )
    return ValidationReport(tuple(issues))
