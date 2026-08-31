# lsmesh

`lsmesh` converts ViennaLS and ViennaPS interfaces into validated,
material-resolved 2D and 3D meshes. It accepts live ViennaPS domains or exported
VTP interfaces, runs Triangle or TetGen, and returns typed Python results with
validation, quality, material, and retry information.

## Installation

```bash
pip install lsmesh
```

Triangle is bundled with the package. Generating 3D tetrahedral meshes requires
the `tetgen` executable to be available on `PATH`.

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

All recoverable library failures derive from `LsmesherError`:

```python
try:
    result = lsmesh.mesh(domain)
except lsmesh.AutomaticMeshingError as error:
    for attempt in error.attempts:
        print(attempt.name, attempt.error)
except lsmesh.MesherNotFoundError as error:
    print(error.mesher)
except lsmesh.LsmesherError as error:
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

The package installs the `lsmesher` command:

```bash
lsmesher --help
lsmesher mesh --help
```

Mesh one or more exported VTP interfaces:

```bash
lsmesher mesh interface.vtp --out mesh.vtu
lsmesher mesh substrate.vtp oxide.vtp mask.vtp --out mesh.vtu
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
lsmesher mesh --help
```
