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

## Viewer presets

The viewer discovers examples under `viewer_presets/`. Set
`LSMESHER_PRESETS_DIR` to use another preset directory. It can also load local
or uploaded `.vtp`, `.vtu`, `.vtk`, and `.off` files.
