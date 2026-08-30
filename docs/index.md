# Overview

`lsmesh` converts ViennaLS and ViennaPS interfaces into material-resolved 2D
triangle meshes and 3D tetrahedral meshes. It accepts a live ViennaPS domain,
one or more exported VTP interfaces, or an already constructed lsmesh geometry.

For normal use, import everything from `lsmesh`:

```python
import lsmesh

result = lsmesh.mesh(domain)
result.write("device.vtu")
```

`mesh()` performs the complete pipeline:

1. extracts the interfaces from the input;
2. constructs a closed, material-aware boundary;
3. validates that boundary;
4. runs Triangle in 2D or TetGen in 3D;
5. verifies element measures, mesh quality, and material coverage; and
6. returns a typed result with the generated mesh and reports.

The dimension is inferred for standard inputs. It can also be stated explicitly:

```python
result_2d = lsmesh.mesh(domain_2d, dimension=2)
result_3d = lsmesh.mesh(domain_3d, dimension=3)
```

## Inputs

### Live ViennaPS domains

Pass a processed ViennaPS domain directly:

```python
result = lsmesh.mesh(domain, quality="balanced")
```

Material IDs and names are read from the domain's material map and preserved in
the generated element attributes.

### Exported interfaces

A single VTP interface can be passed as a path:

```python
result = lsmesh.mesh("interface.vtp", dimension=3)
```

For several interfaces, order them from the lowest or innermost level set to
the highest or outermost:

```python
result = lsmesh.mesh(
    ["substrate.vtp", "oxide.vtp", "mask.vtp"],
    dimension=3,
)
```

File inputs do not contain the ViennaPS material map. Their generated region
attributes therefore use the interface order rather than application-specific
material IDs.

## Outputs

Omitting the output path keeps `mesh()` free of persistent output files:

```python
result = lsmesh.mesh(domain)
result.write("device.vtu")
```

An output path can be supplied as a convenience:

```python
result = lsmesh.mesh(domain, "device.vtu")
```

The result exposes both the final mesh and the intermediate geometry:

```python
result.mesh
result.geometry
result.materials
result.material_ids
result.validation
result.quality
result.automatic
result.warnings
```

`result.require_mesh()` returns the generated mesh or raises if the operation
was configured to stop after boundary construction.

## Choosing an API level

Use the automatic API unless you need a specific mesher parameter:

```python
result = lsmesh.mesh(domain, quality="accurate")
```

Use `options=` when exact settings and a single attempt are required:

```python
result = lsmesh.mesh(domain, options=lsmesh.MeshOptions(...))
```

Use the individual build, validation, and write operations when integrating
lsmesh into a custom pipeline:

```python
geometry = lsmesh.build_from_viennaps(domain, dimension=3)
report = lsmesh.validate(geometry)
report.raise_for_errors()
lsmesh.write(geometry, "surface.vtp")
```

See [Automatic mesh quality](quality.md) for the high-level presets and
[Lower-level options](options.md) for exact control.
