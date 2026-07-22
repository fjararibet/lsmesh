"""Hatch build hook that compiles Triangle from the vendored source.

Triangle source: http://www.cs.cmu.edu/~quake/triangle.html
Version 1.6, by Jonathan Richard Shewchuk.
"""

import shutil
import subprocess
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


def _run_in_nix_shell(cmd: list[str]) -> None:
    """Run a command in nix-shell if available, otherwise run directly."""
    nix_shell = shutil.which("nix-shell")
    if nix_shell and Path("shell.nix").exists():
        # Run inside nix-shell
        full_cmd = [nix_shell, "--run", " ".join(cmd)]
        subprocess.run(full_cmd, check=True)
    else:
        # Run directly
        subprocess.run(cmd, check=True)


class TriangleBuildHook(BuildHookInterface):
    """Compile the Triangle mesher from vendor/triangle and place it in the package."""

    PLUGIN_NAME = "triangle-build"

    def initialize(self, version: str, build_data: dict) -> None:  # noqa: ARG002
        """Compile Triangle and Show Me binaries and stage them into src/lsmesher/bin/."""
        if self.target_name != "wheel":
            return

        # The bundled executables make this a platform-specific wheel. Without
        # these flags Hatchling would incorrectly label it as py3-none-any.
        build_data["pure_python"] = False
        build_data["infer_tag"] = True

        root = Path(self.root)
        vendor_dir = root / "vendor" / "triangle"
        bin_dir = root / "src" / "lsmesher" / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)

        cc = shutil.which("cc") or shutil.which("gcc")
        if cc is None:
            msg = "No C compiler found. Install gcc or clang."
            raise RuntimeError(msg)

        # Build triangle binary
        triangle_source = vendor_dir / "triangle.c"
        triangle_output = bin_dir / "triangle"
        triangle_cmd = [
            cc,
            "-O2",
            "-DLINUX",
            "-o",
            str(triangle_output),
            str(triangle_source),
            "-lm",
        ]
        _run_in_nix_shell(triangle_cmd)
        sys.stdout.write(f"Built Triangle binary: {triangle_output}\n")

        # Build showme binary (requires X11)
        showme_source = vendor_dir / "showme.c"
        showme_output = bin_dir / "showme"
        showme_cmd = [
            cc,
            "-O2",
            "-DLINUX",
            "-I/usr/X11R6/include",
            "-L/usr/X11R6/lib",
            "-o",
            str(showme_output),
            str(showme_source),
            "-lX11",
        ]
        _run_in_nix_shell(showme_cmd)
        sys.stdout.write(f"Built Show Me binary: {showme_output}\n")

        # Make sure hatchling includes the binaries in the wheel.
        build_data["force_include"] = {
            str(triangle_output): "lsmesher/bin/triangle",
            str(showme_output): "lsmesher/bin/showme",
        }
