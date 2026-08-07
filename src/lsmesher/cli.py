"""CLI module for lsmesher."""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

import vtk

from lsmesher._bin import SHOWME, TRIANGLE
from lsmesher.api import BuildOptions
from lsmesher.errors import LsmesherError
from lsmesher.meshing import (
    MesherOptions as SdkMesherOptions,
)
from lsmesher.meshing import (
    MeshingOptions,
)
from lsmesher.meshing import (
    mesh as mesh_geometry,
)
from lsmesher.pipeline_3d import (
    DEFAULT_TARGET_TOTAL_FACES,
    DecimationOptions3D,
)


def detect_format_from_extension(filename: str | Path) -> str:
    """Detect output format from file extension.

    Args:
        filename: Output file path.

    Returns:
        Format string: 'poly', 'off', 'vtp', or 'vtu'.
    """
    ext = Path(filename).suffix.lower()
    format_map = {
        ".off": "off",
        ".vtp": "vtp",
        ".vtu": "vtu",
        ".poly": "poly",
    }
    return format_map.get(ext, "poly")


def detect_dimension(vtp_file: str) -> int:
    """Detect if VTP contains 2D lines or 3D surface mesh.

    Args:
        vtp_file: Path to VTP file.

    Returns:
        2 for 2D (lines), 3 for 3D (polygons).

    Raises:
        ValueError: If VTP has neither lines nor polygons, or has both.
    """
    reader = vtk.vtkXMLPolyDataReader()
    reader.SetFileName(str(vtp_file))
    reader.Update()
    polydata = reader.GetOutput()

    has_lines = polydata.GetLines().GetNumberOfCells() > 0
    has_polys = polydata.GetPolys().GetNumberOfCells() > 0

    if has_lines and not has_polys:
        return 2
    if has_polys and not has_lines:
        return 3

    msg = (
        f"Cannot auto-detect dimension: {polydata.GetLines().GetNumberOfCells()} lines, "
        f"{polydata.GetPolys().GetNumberOfCells()} polygons. "
        "VTP must contain either lines (2D) or polygons (3D), not both or neither."
    )
    raise ValueError(msg)


class CliArgs(Protocol):
    """Protocol for CLI arguments."""

    files: list[str]
    epsilon: float
    format: Literal["poly", "off", "vtp", "vtu"]
    out: str | None
    no_mesh: bool
    no_holes: bool
    verbose: bool


@dataclass(frozen=True)
class MesherOptions:
    """Combined CLI controls split across SDK build and mesher options."""

    triangle_min_angle: float = 20.0
    tetgen_quality_ratio: float = 2.0
    tetgen_min_dihedral: float = 0.0
    tetgen_max_volume: float | None = None
    bottom_margin: float = 0.10
    seam_protection_rings: int = 8


def _sdk_mesher_options(options: MesherOptions) -> SdkMesherOptions:
    return SdkMesherOptions(
        triangle_min_angle=options.triangle_min_angle,
        tetgen_quality_ratio=options.tetgen_quality_ratio,
        tetgen_min_dihedral=options.tetgen_min_dihedral,
        tetgen_max_volume=options.tetgen_max_volume,
    )


def mesher_options_from_args(args: CliArgs) -> MesherOptions:
    """Build mesher options from parsed CLI or viewer arguments."""
    explicit = getattr(args, "mesher", None)
    if explicit is not None:
        return explicit

    defaults = MesherOptions()
    return MesherOptions(
        triangle_min_angle=getattr(
            args, "triangle_min_angle", defaults.triangle_min_angle
        ),
        tetgen_quality_ratio=getattr(
            args, "tetgen_quality_ratio", defaults.tetgen_quality_ratio
        ),
        tetgen_min_dihedral=getattr(
            args, "tetgen_min_dihedral", defaults.tetgen_min_dihedral
        ),
        tetgen_max_volume=getattr(
            args, "tetgen_max_volume", defaults.tetgen_max_volume
        ),
        bottom_margin=getattr(args, "bottom_margin", defaults.bottom_margin),
        seam_protection_rings=getattr(
            args, "seam_protection_rings", defaults.seam_protection_rings
        ),
    )


def _triangle_switches(options: MesherOptions) -> str:
    return f"-pDq{options.triangle_min_angle:g}gA"


def run_2d(args: CliArgs) -> None:
    """Run the 2D meshing pipeline."""
    if not args.out:
        return
    mesher = mesher_options_from_args(args)
    mesh_geometry(
        args.files,
        args.out,
        dimension=2,
        options=MeshingOptions(
            build=BuildOptions(
                epsilon=args.epsilon,
                detect_holes=not args.no_holes,
                random_seed=getattr(args, "random_seed", None),
            ),
            mesher=_sdk_mesher_options(mesher),
            run_mesher=not args.no_mesh,
            validate=not getattr(args, "no_validate", False),
        ),
    )


def _tetgen_switches(options: MesherOptions) -> str:
    quality = f"q{options.tetgen_quality_ratio:g}"
    if options.tetgen_min_dihedral > 0:
        quality += f"/{options.tetgen_min_dihedral:g}"
    volume = (
        f"a{options.tetgen_max_volume:g}"
        if options.tetgen_max_volume is not None
        else ""
    )
    return f"-p{quality}AkR{volume}"


def decimation_options_from_args(args: CliArgs) -> DecimationOptions3D:
    """Build 3D decimation options from parsed CLI or viewer arguments.

    A ready-made ``args.decimation`` options object takes precedence;
    otherwise individual ``decimate_*`` attributes are read, falling back to
    the `DecimationOptions3D` defaults when absent.
    """
    explicit = getattr(args, "decimation", None)
    if explicit is not None:
        return explicit

    defaults = DecimationOptions3D()
    return DecimationOptions3D(
        enabled=not getattr(args, "no_decimate", False),
        target_total_faces=getattr(
            args, "decimate_target_total_faces", defaults.target_total_faces
        ),
        target_edge_length=getattr(
            args, "decimate_target_edge_length", defaults.target_edge_length
        ),
        target_faces=getattr(args, "decimate_target_faces", defaults.target_faces),
        quality_threshold=getattr(args, "decimate_quality", defaults.quality_threshold),
        preserve_boundary=getattr(
            args, "decimate_preserve_boundary", defaults.preserve_boundary
        ),
        boundary_weight=getattr(
            args, "decimate_boundary_weight", defaults.boundary_weight
        ),
        optimal_placement=getattr(
            args, "decimate_optimal_placement", defaults.optimal_placement
        ),
        planar_quadric=getattr(
            args, "decimate_planar_quadric", defaults.planar_quadric
        ),
        planar_weight=getattr(args, "decimate_planar_weight", defaults.planar_weight),
    )


def run_3d(args: CliArgs) -> None:
    """Run the 3D meshing pipeline."""
    if not args.out:
        return
    mesher = mesher_options_from_args(args)
    mesh_geometry(
        args.files,
        args.out,
        dimension=3,
        options=MeshingOptions(
            build=BuildOptions(
                decimation=decimation_options_from_args(args),
                bottom_margin=mesher.bottom_margin,
                seam_protection_rings=mesher.seam_protection_rings,
            ),
            mesher=_sdk_mesher_options(mesher),
            run_mesher=not args.no_mesh,
            validate=not getattr(args, "no_validate", False),
        ),
    )


def run_triangle(args: argparse.Namespace) -> None:
    """Run the Triangle binary with all passed arguments."""
    os.execv(str(TRIANGLE), [str(TRIANGLE), *args.args])


def run_showme(args: argparse.Namespace) -> None:
    """Run the Show Me binary with all passed arguments."""
    os.execv(str(SHOWME), [str(SHOWME), *args.args])


def _bounded_float(
    value: str,
    *,
    minimum: float,
    maximum: float,
    label: str,
) -> float:
    number = float(value)
    if not minimum <= number <= maximum:
        msg = f"{label} must be between {minimum:g} and {maximum:g}"
        raise argparse.ArgumentTypeError(msg)
    return number


def _positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        msg = "value must be greater than zero"
        raise argparse.ArgumentTypeError(msg)
    return number


def _nonnegative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        msg = "value must be zero or greater"
        raise argparse.ArgumentTypeError(msg)
    return number


def main() -> None:  # noqa: PLR0915
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Merge geometry from VTP files and output POLY/OFF, then run mesher."
    )
    subparsers = parser.add_subparsers(dest="command")

    # Main meshing command (default behavior)
    mesh_parser = subparsers.add_parser(
        "mesh",
        help="Run the meshing pipeline (default)",
        description="Merge geometry from VTP files and output POLY/OFF, then run mesher.",
    )
    mesh_parser.add_argument(
        "files", nargs="+", help="Path to VTP files (2D=lines, 3D=polygons)"
    )
    mesh_parser.add_argument(
        "-e",
        "--epsilon",
        type=float,
        default=1e-6,
        help="Tolerance for collinear point removal (default: 1e-6)",
    )
    mesh_parser.add_argument(
        "--format",
        type=str,
        choices=["poly", "off", "vtp", "vtu"],
        default=None,
        help="Output format: poly, off, vtp, or vtu (default: auto-detect from file extension, fallback to poly)",
    )
    mesh_parser.add_argument(
        "-o",
        "--out",
        help="Output file path",
    )
    mesh_parser.add_argument(
        "--no-mesh",
        action="store_true",
        help="Skip mesher invocation (triangle/tetgen)",
    )
    mesh_parser.add_argument(
        "--no-holes",
        action="store_true",
        help="Skip hole detection sampling (only needed for POLY output)",
    )
    mesh_parser.add_argument(
        "--random-seed",
        type=int,
        default=None,
        metavar="INTEGER",
        help="Seed material-region sampling for reproducible 2D meshes",
    )
    mesh_parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip pre-mesher structural validation",
    )
    mesh_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show mesher output (Triangle; TetGen output is always shown)",
    )
    mesher_defaults = MesherOptions()
    mesh_parser.add_argument(
        "--triangle-min-angle",
        type=lambda value: _bounded_float(
            value,
            minimum=0.0,
            maximum=33.0,
            label="Triangle minimum angle",
        ),
        default=mesher_defaults.triangle_min_angle,
        metavar="DEGREES",
        help=(
            "Minimum Triangle element angle in degrees, from 0 to 33 "
            f"(default: {mesher_defaults.triangle_min_angle:g})"
        ),
    )
    mesh_parser.add_argument(
        "--tetgen-quality-ratio",
        type=lambda value: _bounded_float(
            value,
            minimum=1.1,
            maximum=2.5,
            label="TetGen quality ratio",
        ),
        default=mesher_defaults.tetgen_quality_ratio,
        metavar="RATIO",
        help=(
            "TetGen maximum radius-edge ratio, from 1.1 to 2.5; lower is "
            f"stricter (default: {mesher_defaults.tetgen_quality_ratio:g})"
        ),
    )
    mesh_parser.add_argument(
        "--tetgen-min-dihedral",
        type=lambda value: _bounded_float(
            value,
            minimum=0.0,
            maximum=18.0,
            label="TetGen minimum dihedral angle",
        ),
        default=mesher_defaults.tetgen_min_dihedral,
        metavar="DEGREES",
        help=(
            "TetGen minimum dihedral angle in degrees, from 0 to 18 "
            f"(default: {mesher_defaults.tetgen_min_dihedral:g})"
        ),
    )
    mesh_parser.add_argument(
        "--tetgen-max-volume",
        type=_positive_float,
        default=mesher_defaults.tetgen_max_volume,
        metavar="VOLUME",
        help="Global maximum tetrahedron volume (default: unconstrained)",
    )
    mesh_parser.add_argument(
        "--bottom-margin",
        type=_positive_float,
        default=mesher_defaults.bottom_margin,
        metavar="FRACTION",
        help=(
            "Substrate depth below the lowest surface as a fraction of geometry "
            f"height (default: {mesher_defaults.bottom_margin:g})"
        ),
    )
    mesh_parser.add_argument(
        "--seam-protection-rings",
        type=_nonnegative_int,
        default=mesher_defaults.seam_protection_rings,
        metavar="RINGS",
        help=(
            "Vertex rings protected from decimation around self-touching seams "
            f"(default: {mesher_defaults.seam_protection_rings})"
        ),
    )
    decimation_defaults = DecimationOptions3D()
    mesh_parser.add_argument(
        "--no-decimate",
        action="store_true",
        help="Skip 3D patch decimation",
    )
    target_group = mesh_parser.add_mutually_exclusive_group()
    target_group.add_argument(
        "--decimate-target-total-faces",
        type=_nonnegative_int,
        default=DEFAULT_TARGET_TOTAL_FACES,
        metavar="COUNT",
        help=(
            "Target face budget for the unique 3D patch complex, allocated by "
            f"physical patch area (default: {DEFAULT_TARGET_TOTAL_FACES})"
        ),
    )
    target_group.add_argument(
        "--decimate-target-edge-length",
        type=_positive_float,
        default=None,
        metavar="LENGTH",
        help="Approximate target triangle edge length in model units",
    )
    target_group.add_argument(
        "--decimate-target-faces",
        type=int,
        default=None,
        metavar="COUNT",
        help=("Deprecated compatibility option: fixed target for every 3D patch"),
    )
    mesh_parser.add_argument(
        "--decimate-quality",
        type=float,
        default=decimation_defaults.quality_threshold,
        help=(
            "Quadric quality threshold in [0, 1]; higher avoids skinny "
            f"triangles (default: {decimation_defaults.quality_threshold})"
        ),
    )
    mesh_parser.add_argument(
        "--decimate-preserve-boundary",
        action=argparse.BooleanOptionalAction,
        default=decimation_defaults.preserve_boundary,
        help=(
            "Keep patch boundaries (material junction curves and wall "
            "traces) exactly fixed during decimation. Disabling lets "
            "boundaries move and usually breaks layer conformity "
            "(default: enabled)"
        ),
    )
    mesh_parser.add_argument(
        "--decimate-boundary-weight",
        type=float,
        default=decimation_defaults.boundary_weight,
        help=(
            "Importance of patch boundaries during decimation; only has an "
            "effect with --no-decimate-preserve-boundary "
            f"(default: {decimation_defaults.boundary_weight})"
        ),
    )
    mesh_parser.add_argument(
        "--decimate-optimal-placement",
        action="store_true",
        help=(
            "Place collapsed vertices optimally instead of keeping original "
            "positions (better shapes, slightly higher intersection risk)"
        ),
    )
    mesh_parser.add_argument(
        "--decimate-planar-quadric",
        action=argparse.BooleanOptionalAction,
        default=decimation_defaults.planar_quadric,
        help="Improve simplification of flat regions",
    )
    mesh_parser.add_argument(
        "--decimate-planar-weight",
        type=float,
        default=decimation_defaults.planar_weight,
        help=(
            "Weight of the planar quadric term "
            f"(default: {decimation_defaults.planar_weight})"
        ),
    )

    # Triangle subcommand
    triangle_parser = subparsers.add_parser(
        "triangle",
        help="Run the Triangle mesher (2D Delaunay triangulator)",
        description="Run the Triangle mesher. Pass any Triangle arguments after --",
    )
    triangle_parser.add_argument(
        "args",
        nargs="*",
        help="Arguments to pass to Triangle",
    )

    # Show Me subcommand
    showme_parser = subparsers.add_parser(
        "showme",
        help="Run the Show Me mesh viewer (requires X11)",
        description="Run the Show Me mesh viewer. Pass any Show Me arguments after --",
    )
    showme_parser.add_argument(
        "args",
        nargs="*",
        help="Arguments to pass to Show Me",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)
    elif args.command == "mesh":
        # Auto-detect format from output file extension if not specified
        if args.format is None:
            if args.out:
                args.format = detect_format_from_extension(args.out)
            else:
                args.format = "poly"  # Default when no output file specified

        dim = detect_dimension(args.files[0])
        try:
            if dim == 2:
                run_2d(args)
            else:
                run_3d(args)
        except LsmesherError as error:
            parser.exit(2, f"lsmesher: error: {error}\n")
    elif args.command == "triangle":
        run_triangle(args)
    elif args.command == "showme":
        run_showme(args)


if __name__ == "__main__":
    main()
