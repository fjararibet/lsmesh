# Automatic mesh quality

The `quality=` argument selects an automatic meshing strategy. It derives
scale-aware sizing, checks the generated mesh, and performs bounded recovery —
without requiring Triangle, TetGen, or decimation parameters:

```python
result = lsmesh.mesh(domain, quality="accurate")
```

The default is `"balanced"`, so these calls are equivalent:

```python
lsmesh.mesh(domain)
lsmesh.mesh(domain, quality="balanced")
```

Only `"fast"`, `"balanced"`, and `"accurate"` are accepted. For exact values,
use `options=` instead (see [Lower-level options](options.md)).

## Presets

Policies express intent: they control multipliers and acceptance targets rather
than exposing raw mesher parameters.

| Quality | Surface edge target | Volume edge scale | TetGen ratio | Shape-quality p05 target |
| --- | ---: | ---: | ---: | ---: |
| `fast` | 4 characteristic lengths | 6 characteristic lengths | 2.5 | 0.10 |
| `balanced` | 3 characteristic lengths | 5 characteristic lengths | 2.0 | 0.20 |
| `accurate` | 2 characteristic lengths | 3.5 characteristic lengths | 1.6 | 0.30 |

Smaller surface and volume targets retain more detail and produce more
elements. A smaller TetGen radius-edge ratio is a stricter tetrahedron shape
constraint.

The characteristic length is the grid spacing of a live ViennaPS domain, or the
median unique input-edge length for typed geometries and VTP files. The volume
edge scale is converted to a regular-tetrahedron volume:

```text
maximum_volume = volume_edge^3 / (6 * sqrt(2))
```

In 2D the same API is accepted, but the presets primarily drive the 3D surface
and tetrahedral pipeline; Triangle uses its configured minimum-angle
constraint.

## Bounded recovery

Automatic mode makes at most three attempts:

1. **scale-aware** — the selected quality's initial settings;
2. **safer-surface** — 33% smaller surface target, no optimal vertex placement,
   and a wider protected seam neighborhood;
3. **no-decimation-recovery** — original interface triangulation and a relaxed
   TetGen radius-edge ratio.

An attempt is retried when geometry validation, Triangle/TetGen, material
coverage, element correctness, or the requested soft shape-quality target
rejects it. The final attempt may be accepted below the soft target, but never
when a hard correctness check fails.

Explicit `MeshOptions` are an expert escape hatch and run exactly once. The
final quality report is still computed unless meshing is disabled.

## Correctness checks

After external meshing, lsmesh requires:

- at least one element;
- strictly positive triangle area or tetrahedron signed volume;
- every expected material ID present in the element attributes;
- no unknown material ID when a material map is available.

A successful mesher run is not sufficient if a material disappeared or a
zero or inverted element exists. ViennaPS material IDs, including `0`, are
preserved in the final mesh (see [Material Identities](material-identities.md)).

The shape-quality measure is the normalized mean ratio: `1` for an equilateral
triangle or regular tetrahedron, approaching `0` for a degenerate element.

## Reports

Automatic decisions are available on the result:

```python
automatic = result.automatic

print(automatic.quality)              # "fast" | "balanced" | "accurate"
print(automatic.selected_attempt)     # name of the accepted attempt
print(automatic.attempts)             # full per-attempt history
print(automatic.retried)              # whether more than one attempt ran
print(automatic.quality_target_met)   # soft shape-quality target reached
```

Element measurements are separate:

```python
quality = result.quality

print(quality.element_count)
print(quality.minimum_measure)
print(quality.minimum_shape_quality)
print(quality.shape_quality_p05)
print(quality.material_ids)
print(quality.correct)                # hard correctness checks passed
```

When `mesh()` receives an output path, the same information is written to
`<output-stem>.automatic.json` and included in `result.report_paths`. If every
attempt fails, `AutomaticMeshingError` retains the history:

```python
try:
    result = lsmesh.mesh(domain, quality="accurate")
except lsmesh.AutomaticMeshingError as error:
    for attempt in error.attempts:
        print(attempt.name, attempt.error)
```

## Quality versus options

`quality` and `options` cannot be combined:

```python
# Raises ValueError
lsmesh.mesh(domain, quality="accurate", options=lsmesh.MeshOptions())
```

Choose `quality=` for automatic sizing, validation, and recovery. Choose
`options=` when you need exact parameters and one deterministic attempt.
