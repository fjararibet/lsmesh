"""Tests for composable 3D pipeline transformations."""

import argparse
import subprocess
from pathlib import Path

import pytest

from lsmesher import cli
from lsmesher.geometry_types import Face, Point3D, Region3D
from lsmesher.pipeline_3d import (
    DecimationOptions3D,
    _has_fold_edges,
    _split_seam_neighborhood,
    build_3d_surface,
    close_3d_surface,
    collect_3d_regions,
    compute_bottom_points_3d_from_surfaces,
    decimate_3d_patch,
    decimate_conforming_3d_surfaces,
    merge_3d_surfaces,
    surface_3d_to_off_text,
    surface_3d_to_poly_text,
)
from lsmesher.pipeline_types import Surface3D


def sample_surface(offset: float = 0.0) -> Surface3D:
    """Return a small non-flat surface for pipeline tests."""
    return Surface3D(
        points=(
            Point3D(offset + 0.0, 0.0, 0.0),
            Point3D(offset + 1.0, 0.0, 0.0),
            Point3D(offset + 0.0, 1.0, 0.0),
            Point3D(offset + 0.0, 0.0, 1.0),
        ),
        faces=(
            Face((0, 1, 2)),
            Face((0, 1, 3)),
        ),
    )


def square_surface(z: float) -> Surface3D:
    """Return a square surface with all four XY corners present."""
    return Surface3D(
        points=(
            Point3D(0.0, 0.0, z),
            Point3D(1.0, 0.0, z),
            Point3D(0.0, 1.0, z),
            Point3D(1.0, 1.0, z),
        ),
        faces=(Face((0, 1, 3, 2)),),
    )


def strip_surface() -> Surface3D:
    """Return a flat three-quad strip covering x in [0, 3]."""
    return Surface3D(
        points=(
            Point3D(0.0, 0.0, 0.0),
            Point3D(1.0, 0.0, 0.0),
            Point3D(2.0, 0.0, 0.0),
            Point3D(3.0, 0.0, 0.0),
            Point3D(0.0, 1.0, 0.0),
            Point3D(1.0, 1.0, 0.0),
            Point3D(2.0, 1.0, 0.0),
            Point3D(3.0, 1.0, 0.0),
        ),
        faces=(
            Face((0, 1, 5, 4)),
            Face((1, 2, 6, 5)),
            Face((2, 3, 7, 6)),
        ),
    )


def two_bump_surface() -> Surface3D:
    """Return a surface sharing the strip's middle quad with two raised quads."""
    return Surface3D(
        points=(
            Point3D(0.0, 0.0, 1.0),
            Point3D(1.0, 0.0, 1.0),
            Point3D(0.0, 1.0, 1.0),
            Point3D(1.0, 1.0, 1.0),
            Point3D(1.0, 0.0, 0.0),
            Point3D(2.0, 0.0, 0.0),
            Point3D(1.0, 1.0, 0.0),
            Point3D(2.0, 1.0, 0.0),
            Point3D(2.0, 0.0, 1.0),
            Point3D(3.0, 0.0, 1.0),
            Point3D(2.0, 1.0, 1.0),
            Point3D(3.0, 1.0, 1.0),
        ),
        faces=(
            Face((0, 1, 3, 2)),
            Face((4, 5, 7, 6)),
            Face((8, 9, 11, 10)),
        ),
    )


def test_compute_bottom_points_3d_from_surfaces():
    """Bottom points span all surfaces and sit below minimum z."""
    first = sample_surface(offset=0.0)
    second = sample_surface(offset=2.0)

    a, b, c, d = compute_bottom_points_3d_from_surfaces((first, second))

    assert a == Point3D(0.0, 1.0, -0.1)
    assert b == Point3D(3.0, 1.0, -0.1)
    assert c == Point3D(0.0, 0.0, -0.1)
    assert d == Point3D(3.0, 0.0, -0.1)


def test_compute_bottom_points_3d_honors_bottom_margin():
    """The substrate depth is configurable as a geometry-height fraction."""
    a, b, c, d = compute_bottom_points_3d_from_surfaces(
        (sample_surface(),), bottom_margin=0.25
    )

    assert {point.z for point in (a, b, c, d)} == {-0.25}


def test_compute_bottom_points_3d_rejects_flat_surfaces():
    """Flat surfaces preserve the previous zero-height validation."""
    surface = Surface3D(
        points=(Point3D(0.0, 0.0, 1.0), Point3D(1.0, 0.0, 1.0)),
        faces=(Face((0, 1)),),
    )

    with pytest.raises(ValueError, match="zero height"):
        compute_bottom_points_3d_from_surfaces((surface,))


def test_decimate_conforming_3d_surfaces_decimates_shared_patches_once():
    """Patches are decimated once and shared regions stay identical."""
    lower = strip_surface()
    upper = two_bump_surface()
    seen: list[Surface3D] = []

    def recording_decimator(patch: Surface3D) -> Surface3D:
        seen.append(patch)
        return patch

    result = decimate_conforming_3d_surfaces(
        (lower, upper), decimator=recording_decimator
    )

    assert len(seen) == 5
    assert all(len(patch.faces) == 1 for patch in seen)
    assert len(result[0].faces) == 3
    assert len(result[1].faces) == 3
    merged = merge_3d_surfaces(result)
    assert len(merged.faces) == 5


def test_decimate_3d_patch_returns_small_patches_unchanged():
    """Patches at or below the face target are not decimated."""
    patch = square_surface(z=0.0)

    assert decimate_3d_patch(patch) is patch


def grid_surface(side: int) -> Surface3D:
    """Return a flat triangulated grid with side*side cells."""
    points = tuple(
        Point3D(float(x), float(y), 0.0)
        for y in range(side + 1)
        for x in range(side + 1)
    )
    faces: list[Face] = []
    for y in range(side):
        for x in range(side):
            corner = y * (side + 1) + x
            faces.append(Face((corner, corner + 1, corner + side + 2)))
            faces.append(Face((corner, corner + side + 2, corner + side + 1)))
    return Surface3D(points=points, faces=tuple(faces))


def test_decimate_3d_patch_reduces_faces_and_keeps_boundary():
    """Real decimation shrinks a dense patch without touching its boundary."""
    patch = grid_surface(side=10)

    def boundary_points(surface: Surface3D) -> set[tuple[float, float, float]]:
        boundary: dict[tuple[int, int], int] = {}
        for face in surface.faces:
            vertices = face.vertices
            for start, end in zip(vertices, (*vertices[1:], vertices[0]), strict=True):
                key = (min(start, end), max(start, end))
                boundary[key] = boundary.get(key, 0) + 1
        return {
            surface.points[vertex].as_tuple()
            for edge, count in boundary.items()
            if count == 1
            for vertex in edge
        }

    result = decimate_3d_patch(patch, DecimationOptions3D(target_faces=50))

    assert len(result.faces) < len(patch.faces)
    assert boundary_points(result) == boundary_points(patch)


def test_decimate_3d_patch_can_release_the_boundary():
    """Without boundary preservation the patch may simplify its border too."""
    patch = grid_surface(side=10)

    preserved = decimate_3d_patch(patch, DecimationOptions3D(target_faces=4))
    released = decimate_3d_patch(
        patch,
        DecimationOptions3D(
            target_faces=4, preserve_boundary=False, boundary_weight=1.0
        ),
    )

    def boundary_points(surface: Surface3D) -> set[tuple[float, float, float]]:
        boundary: dict[tuple[int, int], int] = {}
        for face in surface.faces:
            vertices = face.vertices
            for start, end in zip(vertices, (*vertices[1:], vertices[0]), strict=True):
                key = (min(start, end), max(start, end))
                boundary[key] = boundary.get(key, 0) + 1
        return {
            surface.points[vertex].as_tuple()
            for edge, count in boundary.items()
            if count == 1
            for vertex in edge
        }

    assert boundary_points(preserved) == boundary_points(patch)
    assert len(released.faces) < len(preserved.faces)
    assert boundary_points(released) != boundary_points(patch)


def test_decimate_3d_patch_honors_target_faces_option():
    """A target above the patch size leaves the patch untouched."""
    patch = grid_surface(side=10)

    result = decimate_3d_patch(patch, DecimationOptions3D(target_faces=500))

    assert result is patch


def pinched_surface() -> Surface3D:
    """Return a surface whose sheets touch along one edge shared by four faces."""
    return Surface3D(
        points=(
            Point3D(0.0, 0.0, 0.0),
            Point3D(0.0, 1.0, 0.0),
            Point3D(-1.0, 0.5, -1.0),
            Point3D(1.0, 0.5, -1.0),
            Point3D(-1.0, 0.5, 1.0),
            Point3D(1.0, 0.5, 1.0),
        ),
        faces=(
            Face((0, 1, 2)),
            Face((0, 1, 3)),
            Face((0, 1, 4)),
            Face((0, 1, 5)),
        ),
    )


def test_has_fold_edges_flags_fold_over_flaps():
    """A duplicated face attached to a strip creates an odd edge count."""
    folded = Surface3D(
        points=(
            Point3D(0.0, 0.0, 0.0),
            Point3D(1.0, 0.0, 0.0),
            Point3D(0.0, 1.0, 0.0),
            Point3D(1.0, 1.0, 0.0),
        ),
        faces=(
            Face((0, 1, 2)),
            Face((1, 3, 2)),
            Face((2, 0, 1)),
        ),
    )

    assert _has_fold_edges(folded)


def test_has_fold_edges_accepts_boundaries_and_pinch_seams():
    """Boundary edges and even-count pinch seams are not folds."""
    assert not _has_fold_edges(grid_surface(side=3))
    assert not _has_fold_edges(pinched_surface())


def test_split_seam_neighborhood_protects_faces_near_seams():
    """Faces within the ring distance of a seam are split off unchanged."""
    strip = strip_surface()
    seamed = Surface3D(
        points=(
            *strip.points,
            Point3D(0.0, 0.5, 1.0),
            Point3D(0.0, 0.5, -1.0),
        ),
        faces=(*strip.faces, Face((0, 4, 8)), Face((0, 4, 9))),
    )

    protected, remainder = _split_seam_neighborhood(seamed, rings=1)

    assert protected is not None
    assert remainder is not None
    assert len(protected.faces) == 3
    assert len(remainder.faces) == 2


def test_split_seam_neighborhood_passes_seamless_patches_through():
    """A patch without self-touching seams is returned whole for decimation."""
    patch = grid_surface(side=3)

    protected, remainder = _split_seam_neighborhood(patch)

    assert protected is None
    assert remainder is patch


def test_decimate_conforming_3d_surfaces_never_decimates_pinched_faces():
    """Every face of a fully pinched surface bypasses the decimator."""
    calls: list[Surface3D] = []

    def recording_decimator(patch: Surface3D) -> Surface3D:
        calls.append(patch)
        return patch

    result = decimate_conforming_3d_surfaces(
        (pinched_surface(),), decimator=recording_decimator
    )

    assert not calls
    assert len(result[0].faces) == 4


def test_decimate_conforming_3d_surfaces_honors_zero_seam_rings():
    """Zero protected rings allows a pinched patch to reach the decimator."""
    calls: list[Surface3D] = []

    def recording_decimator(patch: Surface3D) -> Surface3D:
        calls.append(patch)
        return patch

    decimate_conforming_3d_surfaces(
        (pinched_surface(),),
        decimator=recording_decimator,
        seam_protection_rings=0,
    )

    assert len(calls) == 1
    assert len(calls[0].faces) == 4


def test_build_3d_surface_can_disable_decimation():
    """Disabled decimation keeps the merged surfaces bit-identical."""
    first = square_surface(z=0.0)
    second = square_surface(z=1.0)

    result = build_3d_surface(
        (first, second),
        decimation=DecimationOptions3D(enabled=False),
    )

    assert result.faces == (Face((0, 1, 3, 2)), Face((4, 5, 7, 6)))


def test_decimation_options_from_args_uses_defaults_for_missing_flags():
    """Namespaces without decimation flags fall back to the defaults."""
    options = cli.decimation_options_from_args(argparse.Namespace())

    assert options == DecimationOptions3D()


def test_decimation_options_from_args_reads_cli_flags():
    """Every decimation flag maps onto the options object."""
    options = cli.decimation_options_from_args(
        argparse.Namespace(
            no_decimate=False,
            decimate_target_faces=500,
            decimate_quality=0.5,
            decimate_boundary_weight=10.0,
            decimate_optimal_placement=True,
            decimate_planar_quadric=False,
            decimate_planar_weight=0.1,
        )
    )

    assert options == DecimationOptions3D(
        enabled=True,
        target_faces=500,
        quality_threshold=0.5,
        boundary_weight=10.0,
        optimal_placement=True,
        planar_quadric=False,
        planar_weight=0.1,
    )


def test_decimation_options_from_args_prefers_explicit_options():
    """A ready-made options object wins over individual flags."""
    explicit = DecimationOptions3D(enabled=False)

    options = cli.decimation_options_from_args(
        argparse.Namespace(decimation=explicit, decimate_target_faces=5)
    )

    assert options is explicit


def test_mesher_options_from_args_reads_quality_and_geometry_flags():
    """All mesher CLI values map onto the shared options object."""
    options = cli.mesher_options_from_args(
        argparse.Namespace(
            triangle_min_angle=28.0,
            tetgen_quality_ratio=1.4,
            tetgen_min_dihedral=15.0,
            tetgen_max_volume=0.025,
            bottom_margin=0.3,
            seam_protection_rings=4,
        )
    )

    assert options == cli.MesherOptions(
        triangle_min_angle=28.0,
        tetgen_quality_ratio=1.4,
        tetgen_min_dihedral=15.0,
        tetgen_max_volume=0.025,
        bottom_margin=0.3,
        seam_protection_rings=4,
    )
    assert cli._triangle_switches(options) == "-Dq28gA"  # noqa: SLF001
    assert cli._tetgen_switches(options) == "-pq1.4/15AkRa0.025"  # noqa: SLF001


def test_merge_3d_surfaces_concatenates_without_stitching():
    """Merged surfaces keep input faces and add no side-wall triangles."""
    first = square_surface(z=0.0)
    second = square_surface(z=1.0)

    result = merge_3d_surfaces((second, first))

    assert result.points == (*first.points, *second.points)
    assert result.faces == (Face((0, 1, 3, 2)), Face((4, 5, 7, 6)))


def test_merge_3d_surfaces_keeps_shared_faces_once():
    """Coincident faces between conforming surfaces appear exactly once."""
    lower = strip_surface()
    upper = two_bump_surface()

    result = merge_3d_surfaces((lower, upper))

    assert len(result.points) == 16
    assert len(result.faces) == 5
    shared = Face((1, 2, 6, 5))
    assert result.faces.count(shared) == 1


def test_collect_3d_regions_samples_one_point_per_layer():
    """Each layer receives an interior region point with its material ID."""
    surfaces = (square_surface(z=0.0), square_surface(z=1.0))

    regions = collect_3d_regions(surfaces)

    assert regions == (
        Region3D(point=Point3D(0.5, 0.5, -0.05), material=1),
        Region3D(point=Point3D(0.5, 0.5, 0.5), material=2),
    )


def test_collect_3d_regions_samples_each_disconnected_component():
    """Disconnected volumes of one layer all receive the layer's material."""
    regions = collect_3d_regions((strip_surface(), two_bump_surface()))

    upper_regions = [region for region in regions if region.material == 2]
    assert {region.point for region in upper_regions} == {
        Point3D(0.5, 0.5, 0.5),
        Point3D(2.5, 0.5, 0.5),
    }
    assert [region.material for region in regions] == [1, 2, 2]


def test_close_3d_surface_adds_wall_and_bottom_facets():
    """Open boundaries on bounding box walls become closure facets."""
    merged = merge_3d_surfaces((square_surface(z=0.0), square_surface(z=1.0)))

    result = close_3d_surface(merged)

    assert result.faces == merged.faces
    assert len(result.facets) == 5
    bottom_corners = result.points[-4:]
    assert {point.z for point in bottom_corners} == {-0.1}
    assert {(point.x, point.y) for point in bottom_corners} == {
        (0.0, 0.0),
        (1.0, 0.0),
        (0.0, 1.0),
        (1.0, 1.0),
    }
    bottom_facet = result.facets[-1]
    assert len(bottom_facet) == 1
    assert len(bottom_facet[0].vertices) == 4
    for wall_facet in result.facets[:-1]:
        assert all(len(polygon.vertices) == 2 for polygon in wall_facet)


def test_close_3d_surface_accepts_near_wall_boundary_edges():
    """Level-set extraction can leave side-wall points slightly off the box."""
    surface = Surface3D(
        points=(
            Point3D(0.0, 0.0, 0.0),
            Point3D(0.99995, 0.0, 0.0),
            Point3D(0.0, 1.0, 0.0),
            Point3D(0.99995, 1.0, 0.0),
            Point3D(0.0, 0.0, 1.0),
            Point3D(1.0, 0.0, 1.0),
            Point3D(0.0, 1.0, 1.0),
            Point3D(1.0, 1.0, 1.0),
        ),
        faces=(Face((0, 1, 3, 2)), Face((4, 5, 7, 6))),
    )

    result = close_3d_surface(surface)

    assert len(result.facets) == 5


def test_close_3d_surface_accepts_faraday_near_wall_boundary_edge():
    """Faraday cage extraction can leave boundary vertices just inside a wall."""
    surface = Surface3D(
        points=(
            Point3D(-2.5, 4.997751712799072, -0.5000767111778259),
            Point3D(-2.5166101455688477, 5.0, -0.5),
            Point3D(-2.5166101455688477, -5.0, -0.5),
            Point3D(-2.5, -5.0, -0.5),
        ),
        faces=(Face((0, 1, 2, 3)),),
    )

    result = close_3d_surface(surface)

    assert len(result.facets) == 5


def test_close_3d_surface_rejects_boundary_edges_off_the_walls():
    """Boundary edges away from the bounding box walls are reported."""
    surface = Surface3D(
        points=(
            Point3D(0.0, 0.0, 0.0),
            Point3D(2.0, 0.0, 0.0),
            Point3D(1.0, 2.0, 1.0),
        ),
        faces=(Face((0, 1, 2)),),
    )

    with pytest.raises(ValueError, match="side wall"):
        close_3d_surface(surface)


def test_build_3d_surface_decimates_merges_and_closes():
    """The build function decimates patch-wise, merges, and closes the volume."""
    first = square_surface(z=0.0)
    second = square_surface(z=1.0)

    result = build_3d_surface((second, first), decimator=lambda patch: patch)

    assert len(result.faces) == 2
    assert all(len(face.vertices) == 4 for face in result.faces)
    assert result.facets
    assert [region.material for region in result.regions] == [1, 2]


def test_build_3d_surface_honors_bottom_margin():
    """The selected substrate margin drives closure and region sampling."""
    result = build_3d_surface(
        (square_surface(z=0.0), square_surface(z=1.0)),
        decimation=DecimationOptions3D(enabled=False),
        bottom_margin=0.25,
    )

    assert {point.z for point in result.points[-4:]} == {-0.25}
    assert result.regions[0].point.z == -0.125


def test_surface_3d_to_poly_text_serializes_surface():
    """TetGen POLY serialization is a pure final step."""
    result = surface_3d_to_poly_text(sample_surface())

    assert result.splitlines()[0] == "4 3 0 0"
    assert result.splitlines()[5:8] == ["2 0 # faces", "1 0", "3 1 2 3"]


def test_surface_3d_to_poly_text_serializes_material_regions():
    """Merged 3D surfaces include TetGen region material records."""
    surface = merge_3d_surfaces((square_surface(z=0.0), square_surface(z=1.0)))

    result = surface_3d_to_poly_text(surface)

    assert result.splitlines()[-3:] == [
        "2",
        "1 0.5 0.5 -0.05 1 -1",
        "2 0.5 0.5 0.5 2 -1",
    ]


def test_surface_3d_to_poly_text_serializes_closure_facets():
    """Multi-polygon closure facets use TetGen facet syntax."""
    surface = close_3d_surface(
        merge_3d_surfaces((square_surface(z=0.0), square_surface(z=1.0)))
    )

    lines = surface_3d_to_poly_text(surface).splitlines()

    facet_header = lines[len(surface.points) + 1]
    assert facet_header == "7 0 # faces"
    bottom_polygon = [int(part) for part in lines[-5].split()]
    assert bottom_polygon[0] == 4


def test_surface_3d_to_off_text_serializes_surface():
    """OFF serialization is a pure final step."""
    result = surface_3d_to_off_text(sample_surface())

    assert result.splitlines()[0] == "OFF"
    assert result.splitlines()[1] == "4 2 0"


def test_run_3d_vtp_meshes_poly_sidecar(tmp_path, monkeypatch):
    """VTP output uses a TetGen-compatible POLY sidecar when meshing is enabled."""
    output_path = tmp_path / "mesh.vtp"
    surface = sample_surface()
    tetgen_calls = []

    def write_vtp(path, _points, _faces):
        return Path(path).write_text("vtp", encoding="utf-8")

    monkeypatch.setattr(cli, "build_from_files", lambda *_args, **_kwargs: surface)
    monkeypatch.setattr(cli, "write_vtp_3d", write_vtp)
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda command, **kwargs: (
            tetgen_calls.append((command, kwargs))
            or subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        ),
    )

    cli.run_3d(
        argparse.Namespace(
            files=["input.vtp"],
            format="vtp",
            out=str(output_path),
            no_mesh=False,
            verbose=False,
            mesher=cli.MesherOptions(
                tetgen_quality_ratio=1.4,
                tetgen_min_dihedral=15.0,
                tetgen_max_volume=0.025,
            ),
        )
    )

    poly_path = output_path.with_suffix(".poly")
    assert output_path.read_text(encoding="utf-8") == "vtp"
    assert poly_path.read_text(encoding="utf-8").splitlines()[0] == "4 3 0 0"
    log_path = poly_path.with_name("mesh.tetgen.log")
    assert log_path.read_text(encoding="utf-8").startswith(
        f"Command: tetgen -pq1.4/15AkRa0.025 {poly_path}"
    )
    assert tetgen_calls == [
        (
            ["tetgen", "-pq1.4/15AkRa0.025", str(poly_path)],
            {"check": False, "capture_output": True, "text": True},
        )
    ]


def test_run_3d_reports_tetgen_errors(tmp_path, monkeypatch):
    """TetGen failures include captured output for Streamlit display."""
    output_path = tmp_path / "mesh.vtp"
    surface = sample_surface()

    def write_vtp(path, _points, _faces):
        return Path(path).write_text("vtp", encoding="utf-8")

    def fail_tetgen(command, **_kwargs: object):
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="Opening mesh.poly\nRecovering boundaries...",
            stderr="A facet and a segment exactly intersect.",
        )

    monkeypatch.setattr(cli, "build_from_files", lambda *_args, **_kwargs: surface)
    monkeypatch.setattr(cli, "write_vtp_3d", write_vtp)
    monkeypatch.setattr(cli.subprocess, "run", fail_tetgen)

    with pytest.raises(RuntimeError) as error:
        cli.run_3d(
            argparse.Namespace(
                files=["input.vtp"],
                format="vtp",
                out=str(output_path),
                no_mesh=False,
                verbose=False,
            )
        )

    message = str(error.value)
    assert "TetGen failed with exit code 1" in message
    assert "Recovering boundaries" in message
    assert "A facet and a segment exactly intersect" in message
