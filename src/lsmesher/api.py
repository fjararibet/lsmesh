"""Public Python API for building meshes from files or ViennaPS domains."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol, TypeAlias, cast, overload

from lsmesher.geometry_types import Edge, Face, Point2D, Point3D
from lsmesher.pipeline_2d import (
    AttributeSampler2D,
    build_2d_poly_geometry,
    default_2d_attribute_sampler,
    read_2d_layers,
    seeded_2d_attribute_sampler,
)
from lsmesher.pipeline_3d import (
    BOTTOM_MARGIN,
    SEAM_PROTECTION_RINGS,
    DecimationOptions3D,
    build_3d_surface,
    read_3d_surfaces,
)
from lsmesher.pipeline_types import Geometry2D, Layer2D, Surface3D

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path
    from typing import Any

    from lsmesher.results import MaterialInfo

Dimension: TypeAlias = Literal[2, 3]
BuiltGeometry: TypeAlias = Geometry2D | Surface3D


class ViennaLSMesh(Protocol):
    """Structural type implemented by ``viennals.Mesh``."""

    def getNodes(self) -> Sequence[Sequence[float]]: ...  # noqa: N802

    def getLines(self) -> Sequence[Sequence[int]]: ...  # noqa: N802

    def getTriangles(self) -> Sequence[Sequence[int]]: ...  # noqa: N802


class ViennaPSDomain(Protocol):
    """Minimal part of ``viennaps.Domain`` consumed by lsmesher."""

    def getLevelSets(self) -> Sequence[object]: ...  # noqa: N802

    def getMaterialMap(self) -> ViennaPSMaterialMap: ...  # noqa: N802


class ViennaPSMaterialMap(Protocol):
    """Material lookup operations exposed by ViennaPS."""

    def size(self) -> int: ...

    def getMaterialIdAtIdx(self, index: int) -> int: ...  # noqa: N802

    def getMaterialAtIdx(self, index: int) -> object: ...  # noqa: N802


@dataclass(frozen=True)
class BuildOptions:
    """Geometry construction options shared by file and ViennaPS inputs."""

    epsilon: float = 1e-6
    detect_holes: bool = True
    bottom_margin: float = BOTTOM_MARGIN
    seam_protection_rings: int = SEAM_PROTECTION_RINGS
    decimation: DecimationOptions3D = field(default_factory=DecimationOptions3D)
    random_seed: int | None = None


def _sampler(config: BuildOptions) -> AttributeSampler2D:
    if config.random_seed is None:
        return default_2d_attribute_sampler
    return seeded_2d_attribute_sampler(config.random_seed)


def layer_from_viennals(mesh: ViennaLSMesh) -> Layer2D:
    return Layer2D(
        points=tuple(
            Point2D(float(node[0]), float(node[1])) for node in mesh.getNodes()
        ),
        edges=tuple(Edge(int(line[0]), int(line[1])) for line in mesh.getLines()),
    )


def surface_from_viennals(mesh: ViennaLSMesh) -> Surface3D:
    return Surface3D(
        points=tuple(
            Point3D(float(node[0]), float(node[1]), float(node[2]))
            for node in mesh.getNodes()
        ),
        faces=tuple(Face(tuple(map(int, face))) for face in mesh.getTriangles()),
    )


def _viennals_meshes(
    domain: ViennaPSDomain, dimension: Dimension
) -> tuple[ViennaLSMesh, ...]:
    try:
        import viennals as vls  # noqa: PLC0415
    except ImportError as error:  # pragma: no cover
        msg = "ViennaLS is required to mesh a ViennaPS domain"
        raise RuntimeError(msg) from error

    meshes: list[ViennaLSMesh] = []
    for level_set in domain.getLevelSets():
        mesh = vls.Mesh()
        vls.ToSurfaceMesh(cast("Any", level_set), mesh).apply()
        meshes.append(cast("ViennaLSMesh", mesh))

    if not meshes:
        msg = "ViennaPS domain contains no level sets"
        raise ValueError(msg)

    cells = meshes[0].getLines() if dimension == 2 else meshes[0].getTriangles()
    if not cells:
        msg = f"ViennaPS domain does not contain {dimension}D surface elements"
        raise ValueError(msg)
    return tuple(meshes)


def materials_from_viennaps(domain: ViennaPSDomain) -> tuple[MaterialInfo, ...]:
    """Return the ViennaPS material corresponding to each 1-based region."""
    from lsmesher.results import MaterialInfo  # noqa: PLC0415

    material_map = domain.getMaterialMap()
    return tuple(
        MaterialInfo(
            region=index + 1,
            material_id=material_map.getMaterialIdAtIdx(index),
            name=str(material_map.getMaterialAtIdx(index)).split(".")[-1],
        )
        for index in range(material_map.size())
    )


@overload
def build_from_files(
    files: Sequence[str | Path],
    dimension: Literal[2],
    *,
    options: BuildOptions | None = None,
) -> Geometry2D: ...


@overload
def build_from_files(
    files: Sequence[str | Path],
    dimension: Literal[3],
    *,
    options: BuildOptions | None = None,
) -> Surface3D: ...


def build_from_files(
    files: Sequence[str | Path],
    dimension: Dimension,
    *,
    options: BuildOptions | None = None,
) -> BuiltGeometry:
    """Build a closed geometry from ordered ViennaPS interface VTP files."""
    config = options or BuildOptions()
    if dimension == 2:
        return build_2d_poly_geometry(
            read_2d_layers(files),
            epsilon=config.epsilon,
            detect_holes=config.detect_holes,
            sampler=_sampler(config),
        )
    return build_3d_surface(
        read_3d_surfaces(files),
        decimation=config.decimation,
        bottom_margin=config.bottom_margin,
        seam_protection_rings=config.seam_protection_rings,
    )


@overload
def build_from_viennaps(
    domain: ViennaPSDomain,
    dimension: Literal[2],
    *,
    options: BuildOptions | None = None,
) -> Geometry2D: ...


@overload
def build_from_viennaps(
    domain: ViennaPSDomain,
    dimension: Literal[3],
    *,
    options: BuildOptions | None = None,
) -> Surface3D: ...


def build_from_viennaps(
    domain: ViennaPSDomain,
    dimension: Dimension,
    *,
    options: BuildOptions | None = None,
) -> BuiltGeometry:
    """Build a closed geometry directly from a live ``viennaps.Domain``."""
    config = options or BuildOptions()
    meshes = _viennals_meshes(domain, dimension)
    if dimension == 2:
        return build_2d_poly_geometry(
            tuple(layer_from_viennals(mesh) for mesh in meshes),
            epsilon=config.epsilon,
            detect_holes=config.detect_holes,
            sampler=_sampler(config),
        )
    return build_3d_surface(
        tuple(surface_from_viennals(mesh) for mesh in meshes),
        decimation=config.decimation,
        bottom_margin=config.bottom_margin,
        seam_protection_rings=config.seam_protection_rings,
    )
