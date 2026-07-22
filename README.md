# lsmesh

The `lsmesh` distribution provides the `lsmesher` Python package. It converts
2D and 3D ViennaLS/ViennaPS interface files into polygonal and volume meshes and
includes a command-line interface and a Streamlit/PyVista viewer with runnable
example presets.

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

For a library-only installation, viewer dependencies are optional:

```bash
uv add lsmesh
uv add "lsmesh[viewer]"  # only when the Streamlit viewer is needed
```

## Python API and ViennaPS

`mesh()` accepts a live ViennaPS domain, extracts its ordered level sets in
memory, validates the generated geometry, runs Triangle or TetGen, and writes
the requested result:

```python
import viennaps as vps

from lsmesher import mesh

vps.setDimension(3)
domain = vps.Domain()
vps.MakeTrench(
    domain,
    gridDelta=0.25,
    xExtent=20.0,
    yExtent=20.0,
    trenchWidth=6.0,
    trenchDepth=5.0,
).apply()

# Apply ViennaPS processes here, then create a material-resolved volume mesh.
result = mesh(
    domain,
    "device.vtu",
)

print(result.mesh)
print(result.materials)
print(result.automatic)
print(result.quality)
print(result.validation.issues if result.validation else ())
print(result.log_path)
```

The SDK infers the dimension and uses the ViennaPS grid spacing to choose
surface and volume resolution. It validates material coverage and element
quality and performs bounded safer retries when necessary. Use `policy="fast"`
or `policy="accurate"` to express a different goal; explicit `MeshingOptions`
remain available as the expert override. See
[automatic meshing](docs/automatic-meshing.md) for the policy and recovery
contract.

For live domains, Triangle/TetGen and the resulting VTU use ViennaPS material
IDs directly, so
disconnected or repeated layers of the same material share one ID.
`result.materials` retains the corresponding level-set order and names.

Lower-level workflows can use `build_from_viennaps()`, `build_from_files()`,
`validate()`, and `write()` independently. Material-region sampling can be made
reproducible with `BuildOptions(random_seed=42)`. Mesher failures raise
`TriangleError` or `TetGenError` and retain the command, captured output, return
code, and log path.

For exported VTP interfaces, pass the paths directly to `mesh()` or
`build_from_files()`, ordered from the lowest/innermost level set to the
topmost one.

## Viewer presets

The viewer discovers examples under `viewer_presets/`. Set
`LSMESHER_PRESETS_DIR` to use another preset directory. It can also load local
or uploaded `.vtp`, `.vtu`, `.vtk`, and `.off` files.

Presets are ordinary ViennaPS scripts that finish with
`run_preset(domain, dimension=...)`. The live domain is meshed through the SDK
in an isolated subprocess, preserving ViennaPS material identities without
exporting intermediate interfaces. See
[SDK viewer presets](docs/sdk-viewer-presets.md) for the three-file preset
layout and a minimal example.
