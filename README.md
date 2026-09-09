# lsmesh

`lsmesh` converts ViennaLS and ViennaPS interfaces into validated,
material-resolved 2D and 3D meshes. It accepts live ViennaPS domains or exported
VTP interfaces, runs Triangle or TetGen, and returns typed Python results with
validation, quality, material, and retry information.

## Installation

```bash
uv add lsmesh
```

Triangle is bundled with the package. Generating 3D tetrahedral meshes requires
the `tetgen` executable to be available on `PATH`.

### Using the library from another flake

The flake exports `packages.x86_64-linux.lsmesh` (also `default`) and
`overlays.default`. Use the overlay to add `lsmesh` to the same Python package
set as the rest of your project:

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    lsmesh.url = "github:fjararibet/lsmesh/main";
    lsmesh.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { nixpkgs, lsmesh, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        overlays = [ lsmesh.overlays.default ];
      };
      python = pkgs.python3.withPackages (ps: [ ps.lsmesh ]);
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        packages = [ python pkgs.uv ];
        env.UV_PYTHON = "${python}/bin/python";
      };
    };
}
```

Inside `nix develop`, run `uv run --no-project script.py` to use that Nix Python
environment. Add other Python dependencies to `withPackages`; an independently
managed uv virtual environment will not automatically inherit Nix's packages.
If you package the consuming project with `buildPythonPackage`, include
`pkgs.python3Packages.lsmesh` in its `dependencies` instead.

The Nix package includes Triangle and resolves TetGen by its Nix store path,
so library callers need no extra compiler or `PATH` setup. It uses Nixpkgs'
NumPy, SciPy, VTK, and PyMeshLab, and the ViennaLS/ViennaPS wheels pinned in
this repository's `uv.lock`. SciPy and VTK version bounds are relaxed only in
the Nix package to use Nixpkgs' versions. The packaged library currently
supports **x86-64 Linux**; the locked Vienna wheels do not support Linux ARM.
The overlay selects wheels for the chosen CPython version and reports an error
if no matching wheel exists in the lock file.

To pick up the newest pushed commit, run this in the consuming project:

```sh
nix flake update lsmesh
nix develop
```

Flakes retain their pinned commit until updated, even when the input points at
`main`. For automatic updates on entry, use `nix flake update lsmesh && nix develop`.
No PyPI release or package version bump is needed for Git input updates.

From this repository, `nix build .#lsmesh` builds the library and
`nix flake check` checks downstream imports and actual 2D/3D meshing.
`nix run .#cli -- --help` runs the packaged CLI on x86-64 Linux.
`nix run .` and `nix run .#docs` remain development launchers intended to run
from this checkout.

## Python API

Create a mesh directly from a live ViennaPS domain:

```python
import viennaps as vps

import lsmesh

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

# Apply additional ViennaPS processes here.

result = lsmesh.mesh(domain)
result.write("device.vtu")

print(result.quality.summary())
print(result.materials)
print(result.warnings)
```

An output path can also be passed directly:

```python
result = lsmesh.mesh(domain, "device.vtu")
```

### Automatic policies

Automatic meshing infers the dimension and characteristic length, validates the
geometry, checks element quality and material coverage, and performs bounded
recovery attempts when necessary. The default quality is `balanced`:

```python
fast = lsmesh.mesh(domain, quality="fast")
balanced = lsmesh.mesh(domain, quality="balanced")
accurate = lsmesh.mesh(domain, quality="accurate")
```

Explicit options are available when direct control is needed. `quality` and
`options` are mutually exclusive:

```python
options = lsmesh.MeshOptions(
    build=lsmesh.BuildOptions(
        epsilon=1e-6,
        random_seed=42,
        decimation=lsmesh.DecimationOptions3D(
            target_edge_length=0.5,
        ),
    ),
    mesher=lsmesh.MesherOptions(
        tetgen_quality_ratio=1.5,
        tetgen_max_volume=0.25,
    ),
)

result = lsmesh.mesh(domain, options=options)
```

### Exported VTP interfaces

A single interface path can be passed directly:

```python
result = lsmesh.mesh("interface.vtp", dimension=3)
result.write("mesh.vtu")
```

For multiple interfaces, order paths from the lowest or innermost level set to
the highest or outermost:

```python
result = lsmesh.mesh(
    ["substrate.vtp", "oxide.vtp", "mask.vtp"],
    dimension=3,
)
result.write("mesh.vtu")
```

### Results

`mesh()` returns `MeshResult2D` or `MeshResult3D`. Commonly used fields and
operations include:

```python
result.mesh             # Triangle or TetGen mesh data
result.geometry         # Constructed boundary geometry
result.materials        # ViennaPS material metadata
result.material_ids     # Material IDs in level-set order
result.validation       # Structural validation report
result.quality          # Element and material quality report
result.automatic        # Requested quality and automatic retry report
result.output_path      # Primary output, when written by mesh()
result.report_paths     # Generated JSON sidecars
result.log_path         # Triangle or TetGen process log
result.warnings         # Combined validation and automatic warnings

mesh_data = result.require_mesh()
result.write("another-output.vtu")
```

### Errors

All recoverable library failures derive from `LsmeshError`:

```python
try:
    result = lsmesh.mesh(domain)
except lsmesh.AutomaticMeshingError as error:
    for attempt in error.attempts:
        print(attempt.name, attempt.error)
except lsmesh.MesherNotFoundError as error:
    print(error.mesher)
except lsmesh.LsmeshError as error:
    print(error)
```

`TriangleError` and `TetGenError` retain the executed command, return code,
captured output, and log path.

### Lower-level operations

Important types and functions are available directly from `lsmesh`:

```python
geometry = lsmesh.build_from_viennaps(domain, dimension=3)
report = lsmesh.validate(geometry)
lsmesh.write(geometry, "surface.vtp")
```

Focused modules are also provided for discoverability:

```python
from lsmesh.build import BuildOptions, build_from_files
from lsmesh.errors import TetGenError
from lsmesh.geometry import Surface3D
from lsmesh.options import MeshOptions
```

See [`docs/examples/`](docs/examples) for complete ViennaPS scripts using lsmesh.

## Command-line interface

The package installs the `lsmesh` command:

```bash
lsmesh --help
lsmesh mesh --help
```

Mesh one or more exported VTP interfaces:

```bash
lsmesh mesh interface.vtp --out mesh.vtu
lsmesh mesh substrate.vtp oxide.vtp mask.vtp --out mesh.vtu
```

Input dimension is detected from the VTP cell type: lines are treated as 2D
interfaces and polygons as 3D surfaces.

Useful options include:

```text
--format {poly,off,vtp,vtu}       Output format
--no-mesh                         Build boundary geometry without Triangle/TetGen
--no-validate                     Skip structural validation
--random-seed INTEGER             Reproducible 2D region sampling
--triangle-min-angle DEGREES      Triangle minimum element angle
--tetgen-quality-ratio RATIO      TetGen radius-edge quality bound
--tetgen-min-dihedral DEGREES     TetGen minimum dihedral angle
--tetgen-max-volume VOLUME        Maximum tetrahedron volume
--no-decimate                     Disable 3D surface decimation
--decimate-target-edge-length L   Target 3D surface edge length
--decimate-target-total-faces N   Global 3D surface face budget
```

For the complete option reference:

```bash
lsmesh mesh --help
```
