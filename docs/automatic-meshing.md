# Automatic Meshing

The default Python SDK path chooses scale-aware settings, checks the generated
mesh, and performs bounded recovery without requiring Triangle, TetGen, or
decimation parameters:

```python
result = mesh(domain, "device.vtu")
```

For typed `Geometry2D` and `Surface3D` inputs, and for `viennaps.d2.Domain` and
`viennaps.d3.Domain`, the dimension is inferred. File lists are inferred from
whether their first VTP contains lines or polygons. Pass `dimension=2` or `3`
only when a custom domain type cannot be identified.

## Policies

The default is `balanced`:

```python
mesh(domain, "device.vtu", policy="fast")
mesh(domain, "device.vtu", policy="balanced")
mesh(domain, "device.vtu", policy="accurate")
```

Policies express intent. They control multipliers and acceptance targets rather
than exposing raw mesher parameters:

| Policy | Interface edge target | Volume edge scale | TetGen ratio | Shape-quality p05 |
| --- | ---: | ---: | ---: | ---: |
| `fast` | 4 grid cells | 6 grid cells | 2.5 | 0.10 |
| `balanced` | 3 grid cells | 5 grid cells | 2.0 | 0.20 |
| `accurate` | 2 grid cells | 3.5 grid cells | 1.6 | 0.30 |

The volume edge scale is converted to a regular-tetrahedron volume:

```text
maximum_volume = volume_edge^3 / (6 * sqrt(2))
```

For a live ViennaPS domain, the characteristic length is `getGridDelta()`.
Typed geometries and file inputs fall back to the median unique input-edge
length. If neither is available, the existing conservative global face budget
is used.

These are starting estimates. Local-feature-aware sizing for thin films and
approaching sheets is intentionally deferred to
[its dedicated plan](local-feature-aware-sizing-plan.md).

## Bounded Recovery

Automatic mode makes at most three attempts:

1. **scale-aware** — policy-derived surface edge length and TetGen volume;
2. **safer-surface** — 33% smaller surface target, no optimal vertex placement,
   and a wider protected seam neighborhood;
3. **no-decimation-recovery** — original interface triangulation and a relaxed
   TetGen radius-edge ratio.

An attempt is retried when geometry validation, Triangle/TetGen, material
coverage, element correctness, or the policy's soft quality target rejects it.
The final attempt may be accepted below the soft shape-quality target, but never
when a hard correctness check fails.

Explicit `MeshingOptions` remain an expert escape hatch and run exactly once:

```python
result = mesh(
    domain,
    "device.vtu",
    options=MeshingOptions(...),
)
```

## Correctness Checks

After external meshing, lsmesher requires:

- at least one element;
- strictly positive triangle area or tetrahedron signed volume;
- every expected ViennaPS material ID in the element attributes;
- and no unknown material ID when a live-domain material map is available.

This complements the pre-mesher structural validation. TetGen returning success
is not sufficient if a material disappeared or a zero/inverted element exists.
ViennaPS IDs, including material `0`, are preserved through a reversible
external-mesher encoding described in [Material Identities](material-identities.md).

The current quality measure is the normalized mean-ratio shape quality. It is
`1` for an equilateral triangle or regular tetrahedron and approaches `0` for a
degenerate element. Reports include its minimum and fifth percentile together
with edge ratios, element measures, edge-length range, and material coverage.

## Reporting

Automatic results expose decisions directly:

```python
print(result.automatic.policy)
print(result.automatic.selected_attempt)
print(result.automatic.attempts)
print(result.automatic.quality_target_met)
print(result.quality.shape_quality_p05)
```

The same information is written to `<output-stem>.automatic.json` and included
in `result.output_paths`. Failed attempts record their name, sizing values,
decimation state, and error. The viewer displays a compact summary when this
sidecar exists.
