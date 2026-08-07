# Automatic mesh quality

The `quality=` argument selects an automatic meshing strategy:

```python
fast = lsmesh.mesh(domain, quality="fast")
balanced = lsmesh.mesh(domain, quality="balanced")
accurate = lsmesh.mesh(domain, quality="accurate")
```

The default is `"balanced"`, so these calls are equivalent:

```python
lsmesh.mesh(domain)
lsmesh.mesh(domain, quality="balanced")
```

## Why it is called quality

`quality` describes the result you want rather than a complete configuration.
lsmesh translates that intent into surface simplification, volume sizing,
mesher constraints, acceptance thresholds, and recovery attempts.

It is not an arbitrary config name: only `"fast"`, `"balanced"`, and
`"accurate"` are accepted. For exact values, use `options=` instead.

## Presets

| Quality | Surface edge target | Volume edge scale | TetGen ratio | Shape-quality p05 target |
| --- | ---: | ---: | ---: | ---: |
| `fast` | 4 characteristic lengths | 6 characteristic lengths | 2.5 | 0.10 |
| `balanced` | 3 characteristic lengths | 5 characteristic lengths | 2.0 | 0.20 |
| `accurate` | 2 characteristic lengths | 3.5 characteristic lengths | 1.6 | 0.30 |

Smaller surface and volume targets generally retain more detail and produce
more elements. A smaller TetGen radius-edge ratio is a stricter tetrahedron
quality constraint.

For a live ViennaPS domain, the characteristic length is its grid spacing. For
typed geometry and VTP inputs, lsmesh uses the median unique input-edge length.
The volume edge scale is converted to a regular-tetrahedron volume:

```text
maximum_volume = volume_edge^3 / (6 * sqrt(2))
```

In 2D, the same API is accepted, but the current presets primarily affect the
3D surface and tetrahedral pipeline. Triangle uses its configured minimum-angle
constraint.

## Automatic recovery

Automatic mode makes at most three attempts:

1. `scale-aware` uses the selected quality's initial settings.
2. `safer-surface` uses a 33% smaller surface target, disables optimal vertex
   placement, and protects a wider neighborhood around material seams.
3. `no-decimation-recovery` retains the original interface triangulation and
   relaxes the TetGen radius-edge ratio.

lsmesh retries when an attempt fails geometry validation, external meshing,
material coverage, element correctness, or the requested soft shape-quality
target. The last attempt may be accepted below the soft target, but hard
correctness failures are never accepted.

## Reports

Automatic decisions are available on the result:

```python
automatic = result.automatic

print(automatic.quality)
print(automatic.selected_attempt)
print(automatic.attempts)
print(automatic.retried)
print(automatic.quality_target_met)
```

Element measurements are separate:

```python
print(result.quality.element_count)
print(result.quality.minimum_measure)
print(result.quality.minimum_shape_quality)
print(result.quality.shape_quality_p05)
print(result.quality.material_ids)
```

When `mesh()` receives an output path, it also writes
`<output-stem>.automatic.json`. If every attempt fails,
`AutomaticMeshingError.attempts` retains the history:

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
lsmesh.mesh(
    domain,
    quality="accurate",
    options=lsmesh.MeshOptions(),
)
```

Choose `quality=` for automatic sizing, validation, and recovery. Choose
`options=` when you need exact parameters and want one deterministic attempt.
