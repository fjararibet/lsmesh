# lsmesher

`lsmesher` converts 2D and 3D ViennaLS/ViennaPS interface files into polygonal
and volume meshes. It includes a command-line interface and a Streamlit/PyVista
viewer with runnable example presets.

## Run with Nix

Launch the viewer from the repository root:

```bash
nix run .
```

Then open <http://localhost:8501>.

Run the CLI through the flake:

```bash
nix run .#cli -- --help
nix run .#cli -- mesh interface_0.vtp -o mesh.vtp
```

The flake also provides a development shell with Python build and native mesh
dependencies:

```bash
nix develop
uv sync --frozen
uv run pytest
```

## Direct commands

Inside `nix develop`, the project entry points are:

```bash
uv run lsmesher --help
uv run lsmesher-viewer
```

## Python API and ViennaPS

`lsmesher` accepts a live ViennaPS domain. It extracts each ordered level set
through ViennaLS in memory, preserving the material-interface structure used by
the meshing pipeline:

```python
import viennaps as vps

from lsmesher import BuildOptions, build_from_viennaps
from lsmesher.pipeline_3d import surface_3d_to_poly_text

vps.setDimension(3)
domain = vps.Domain()
# Build or process the domain as usual.

surface = build_from_viennaps(
    domain,
    dimension=3,
    options=BuildOptions(detect_holes=True),
)
poly_text = surface_3d_to_poly_text(surface)
```

The explicit `dimension` argument follows ViennaPS's process-wide dimension and
lets static type checkers infer `Geometry2D` or `Surface3D`. For exported VTP
interfaces, use `build_from_files(files, dimension=2 | 3)` with files ordered
from the lowest/innermost level set to the topmost one.

## Viewer presets

The viewer discovers examples under `viewer_presets/`. Set
`LSMESHER_PRESETS_DIR` to use another preset directory. It can also load local
or uploaded `.vtp`, `.vtu`, `.vtk`, and `.off` files.
