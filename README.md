# lsmesh

`lsmesh` converts ViennaLS/ViennaPS interfaces into material-resolved 2D
triangle and 3D tetrahedral meshes. Inputs may be a live ViennaPS domain or
exported VTP interfaces. The package constructs and validates the boundary,
runs Triangle or TetGen, and returns mesh data with validation and quality
reports.

## Installation

```bash
uv add lsmesh
```

Triangle is bundled. 3D meshing requires the `tetgen` executable on `PATH`.

## Usage

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

result = lsmesh.mesh(domain, "device.vtu")
print(result.quality.summary())
```

For exported interfaces, pass one path or an ordered list. Multiple interfaces
must be ordered from the lowest/innermost to the highest/outermost level set:

```python
result = lsmesh.mesh(
    ["substrate.vtp", "oxide.vtp", "mask.vtp"],
    "device.vtu",
    dimension=3,
)
```

By default, `mesh()` uses the `balanced` quality policy, which selects sizing,
checks the result, and retries selected failures. Use `quality="fast"` or
`quality="accurate"` to change the policy. For explicit mesher and build
parameters, pass `options=lsmesh.MeshOptions(...)`; `quality` and `options`
cannot be combined.

`mesh()` returns a `MeshResult2D` or `MeshResult3D`. The result provides the
mesh, geometry, material information, validation and quality reports, and
methods to write the mesh. See the [API overview](docs/index.md) and
[examples](docs/examples) for details.

## Command line

```bash
lsmesh mesh interface.vtp --out mesh.vtu
lsmesh mesh --help
```

## Development

Run the application with `nix run .` and the documentation server with
`nix run .#docs`.
