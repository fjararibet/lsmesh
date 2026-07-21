# Area-Scaled 3D Decimation Targets

## Motivation

Patches are topological partitions, not units of geometric size. They are
created wherever face ownership changes between ViennaPS level sets and wherever
an equal-owner region is disconnected. Giving every patch the same face target
therefore makes mesh density depend on the material topology: splitting a
surface into more patches can increase the final face count even when its shape
and area are unchanged.

The default policy instead treats all unique, decimatable patches as one surface
complex and distributes a global budget by true 3D surface area.

## Global Face Budget

Use `target_total_faces` when output size and processing cost are the primary
controls:

```python
from lsmesher import BuildOptions, DecimationOptions3D

options = BuildOptions(
    decimation=DecimationOptions3D(target_total_faces=5_600),
)
```

For patch `i`, with area `A_i`, the initial quota is:

```text
q_i = target_total_faces * A_i / sum(A)
```

Integer targets use largest-remainder allocation. A patch target is capped by
its original triangulated face count, and unused budget is redistributed to
patches that can still use it. This makes the sum of allocated targets match the
global budget whenever the input contains at least that many decimatable faces.

Areas are calculated from cross products in 3D, not from an XY projection.
Coincident patches shared by several input level sets are counted once because
they are decimated once and then copied back to every owner.

The default is 5,600 unique decimatable faces.

CLI equivalent:

```bash
lsmesher mesh interfaces/*.vtp \
  --decimate-target-total-faces 5600 \
  -o device.vtu
```

## Target Edge Length

Use `target_edge_length` when spatial resolution should remain meaningful in
model units as the geometry grows or shrinks:

```python
DecimationOptions3D(target_edge_length=0.25)
```

The target count for each patch is estimated using the area of an equilateral
triangle with edge length `h`:

```text
ideal_face_area = sqrt(3) / 4 * h^2
patch_target = ceil(patch_area / ideal_face_area)
```

PyMeshLab accepts a face count rather than a maximum edge length, so this is an
approximate resolution control. Quadric error still determines where faces are
retained within each patch; the edge-length calculation only assigns the budget
between patches.

CLI equivalent:

```bash
lsmesher mesh interfaces/*.vtp \
  --decimate-target-edge-length 0.25 \
  -o device.vtu
```

`target_total_faces` and `target_edge_length` are mutually exclusive on the
CLI. In Python, edge length takes precedence if both fields are populated.

## Protected Seams And Safety Floors

Self-touching seam neighborhoods are split from a patch before targets are
allocated. Their faces keep the original triangulation and do not consume the
adjustable budget:

```text
achieved unique faces = protected faces + decimated remainder faces
```

Each remainder target is also clamped to a conservative boundary floor when
patch-boundary preservation is enabled. If PyMeshLab changes a fixed boundary
or creates a fold edge, lsmesher retries with a less aggressive target. These
safety mechanisms mean the achieved count can exceed the requested budget.

Conformity and a valid TetGen piecewise-linear complex take priority over
hitting the requested count exactly.

## Reporting

High-level 3D `mesh()` results expose `result.decimation`, and a matching
`<output-stem>.decimation.json` file is written beside the output:

```python
report = result.decimation
print(report.mode)
print(report.requested_faces)
print(report.original_faces)
print(report.achieved_faces)
print(report.protected_faces)
print(report.boundary_limited_faces)
```

`boundary_limited_faces` measures faces retained above the allocated targets
because of boundary floors or safety retries. Counts describe the unique patch
complex before shared patches are copied back to their owning level sets.

The viewer displays the same summary below the processed mesh and includes the
JSON report in preset downloads.

## Legacy Per-Patch Target

`target_faces` and `--decimate-target-faces` remain available only for explicit
compatibility. They retain their old meaning: the same fixed target is applied
to every patch. They are not reinterpreted as global targets.

New code should use `target_total_faces` or `target_edge_length`. The legacy
mode is reported as `legacy_per_patch` so downstream tools can identify it.

Spatially varying resolution for thin films, approaching sheets, curvature,
and junctions is deferred to the
[local-feature-aware sizing plan](local-feature-aware-sizing-plan.md).
