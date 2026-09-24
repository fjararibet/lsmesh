# API overview

`lsmesh` converts ViennaLS/ViennaPS interfaces into material-resolved 2D
triangle and 3D tetrahedral meshes. Inputs may be a live ViennaPS domain,
ordered VTP interfaces, or an `lsmesh` geometry.

```python
import lsmesh

result = lsmesh.mesh(domain)
result.write("device.vtu")
```

## mesh()

```python
lsmesh.mesh(
    source,               # ViennaPS domain, VTP path(s), Geometry2D, or Surface3D
    output=None,          # optional destination path
    *,
    dimension=None,       # 2 or 3; inferred when omitted
    quality="balanced",   # "fast", "balanced", or "accurate"
    options=None,         # exact MeshOptions; one attempt, no recovery
)
```

`mesh()` builds and validates a material-aware boundary, invokes Triangle (2D)
or TetGen (3D), checks element measures and material coverage, and returns a
typed result with quality information.

## Inputs

### Live ViennaPS domains

Pass a processed ViennaPS domain directly:

```python
result = lsmesh.mesh(domain, quality="accurate")
```

Material IDs and names are read from the domain's material map and preserved in
the generated element attributes.

### Exported interfaces

A single VTP interface can be passed as a path:

```python
result = lsmesh.mesh("interface.vtp")
```

Order multiple interfaces from the lowest/innermost to the highest/outermost
level set:

```python
result = lsmesh.mesh(["substrate.vtp", "oxide.vtp", "mask.vtp"])
```

VTP files do not include the ViennaPS material map. Region attributes therefore
follow interface order rather than application-specific material IDs.

### Typed geometries

A `Geometry2D` or `Surface3D` previously produced by `build_from_viennaps()`
or `build_from_files()` can be meshed directly:

```python
geometry = lsmesh.build_from_viennaps(domain, 3)
result = lsmesh.mesh(geometry)
```

## Dimension

The dimension is inferred from typed geometry and ViennaPS domains. VTP files
are classified by cell type (lines for 2D, polygons for 3D). Specify
`dimension` when it cannot be inferred:

```python
result_2d = lsmesh.mesh(domain_2d, dimension=2)
result_3d = lsmesh.mesh(domain_3d, dimension=3)
```

## Output

Without an output path, `mesh()` writes no files:

```python
result = lsmesh.mesh(domain)
result.write("device.vtu")
```

An output path can be supplied as a convenience:

```python
result = lsmesh.mesh(domain, "device.vtu")
```

When an output path is given, reports and logs are written beside it and listed
in `result.report_paths`.

## The result

`mesh()` returns a `MeshResult2D` or `MeshResult3D`:

| Member | Meaning |
| --- | --- |
| `geometry` | The closed boundary (`Geometry2D` or `Surface3D`). |
| `mesh` | Generated elements (`TriangleMesh2D` or `TetrahedralMesh3D`), or `None` when meshing was disabled. |
| `materials` | Tuple of `MaterialInfo(region, material_id, name)`. |
| `material_ids` | Tuple of the contained material IDs. |
| `validation` | `ValidationReport` of the constructed boundary. |
| `quality` | `MeshQualityReport` of the generated elements. |
| `automatic` | `AutomaticMeshReport` in automatic mode, otherwise `None`. |
| `decimation` | `DecimationReport` for 3D inputs, otherwise `None`. |
| `output_path` | Primary output file, or `None` when no output path was given. |
| `report_paths` | Sidecar report files written next to the output. |
| `log_path` | Triangle or TetGen log file, when one was written. |
| `warnings` | Combined validation and automatic-mode warnings. |
| `succeeded` | Whether a mesh was generated. |

`result.require_mesh()` returns the generated mesh or raises if the operation
was configured to stop after boundary construction. `result.write(path)`
writes the mesh, or the boundary when meshing was disabled.

## Errors

All package errors derive from `LsmeshError`:

| Exception | Raised when |
| --- | --- |
| `UnsupportedSourceError` | `source` is not a domain, geometry, or VTP path. |
| `InvalidGeometryError` | Boundary validation failed. |
| `TriangleError` / `TetGenError` | The external mesher failed; both carry its log and output. |
| `AutomaticMeshingError` | Every automatic attempt failed; retains the attempt history. |
| `DependencyError` | An optional runtime dependency is missing. |

`ValueError` is raised directly for argument conflicts, such as combining
`quality` with `options`.

## Choosing an API level

Use automatic quality selection for general use:

```python
result = lsmesh.mesh(domain, quality="accurate")
```

Use `options=` for explicit settings and a single attempt:

```python
result = lsmesh.mesh(domain, options=lsmesh.MeshOptions(...))
```

Use the individual operations below to integrate `lsmesh` into another
pipeline.

See [Automatic mesh quality](quality.md) for the high-level presets and
[Lower-level options](options.md) for exact control.

## Step-by-step operations

The pipeline behind `mesh()` is also exposed as individual functions:

```python
geometry = lsmesh.build_from_viennaps(domain, dimension=3)
report = lsmesh.validate(geometry)
report.raise_for_errors()
lsmesh.write(geometry, "surface.vtp")
```

| Function | Purpose |
| --- | --- |
| `build_from_viennaps(domain, dimension, options=None)` | Build a closed geometry from a live domain. |
| `build_from_files(files, dimension, options=None)` | Build a closed geometry from ordered VTP interfaces. |
| `materials_from_viennaps(domain)` | Return the `MaterialInfo` tuple of a domain. |
| `validate(geometry)` | Return a `ValidationReport` of structural problems. |
| `write(value, output)` | Write a geometry or mesh by destination suffix. |

`ValidationReport.valid` states whether any error-severity issue was found, and
`raise_for_errors()` raises `InvalidGeometryError` if so.

`write()` picks the format from the file suffix:

| Value | `.poly` | `.off` | `.vtp` | `.vtu` |
| --- | :-: | :-: | :-: | :-: |
| `Geometry2D` | yes | | yes | |
| `Surface3D` | yes | yes | yes | |
| `TriangleMesh2D` | | yes | yes | yes |
| `TetrahedralMesh3D` | | | | yes |
