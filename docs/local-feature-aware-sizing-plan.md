# Plan: Local-Feature-Aware 3D Mesh Sizing

Status: **deferred design**. This document specifies the intended implementation
of local-feature-aware sizing so it can be picked up after the automatic
`mesh()` quality presets, correctness gates, and retry ladder are established.

## Objective

A single global face count or edge length cannot represent a device containing
both large planar regions and thin films. Local-feature-aware sizing should keep
enough elements across the smallest material features while allowing isolated,
flat regions to become coarse.

The normal API remains automatic:

```python
result = mesh(domain, "device.vtu")
```

An expert may select or tune the quality preset, but should not need to construct a
sizing field manually:

```python
result = mesh(domain, "device.vtu", quality="accurate")
```

The first implementation is isotropic. Anisotropic boundary-layer elements and
physics/error-driven adaptation are out of scope.

## Meaning of Local Feature Size

At a point `x`, the geometric local feature size is approximated by the distance
to the nearest non-incident surface feature that must remain distinguishable.
For lsmesher this primarily means:

- the thickness between adjacent material interfaces;
- the separation between approaching sheets near pinch-off;
- the distance to material-junction curves and sharp corners;
- surface curvature, so a curved interface is not flattened excessively;
- and the ViennaLS grid spacing, which caps the meaningful input resolution.

Adjacent triangles on the same smooth patch must not report their shared edge as
a zero-sized feature. Coincident copies of a shared ViennaPS interface must also
be identified as one geometric feature before distances are calculated.

The desired isotropic edge length is:

```text
h_raw(x) = min(
    grid_factor * grid_delta,
    thickness(x) / elements_across_feature,
    curvature_limit(x),
    user_or_quality_maximum,
)

h(x) = clamp(h_raw(x), quality_minimum, quality_maximum)
```

A balanced quality should initially require at least three elements across a
material thickness. The accurate quality may require four or five. These values
must be established experimentally rather than embedded as unexplained magic
constants.

## Feature Measurement

### 1. Normalize the surface complex

Use the conforming, deduplicated patch representation already built for 3D
decimation. Keep face-owner information so the estimator can distinguish:

- triangles on the same patch;
- coincident triangles shared by level sets;
- true opposing material interfaces;
- exterior closure walls;
- and protected seam neighborhoods.

Sizing is estimated before destructive decimation. Otherwise an aggressive
initial simplification could erase the thin feature the estimator is meant to
protect.

### 2. Build spatial indices

Build an AABB/BVH index over unique triangles and a second index over material
junction and patch-boundary segments. Query points initially include:

- input vertices;
- triangle centroids;
- edge midpoints for long edges;
- and extra samples in protected or high-curvature regions.

For each sample, find the nearest triangle or constraint segment after excluding
incident faces and geometrically coincident shared faces. Record both the
distance and the owning material/interface pair; this makes bad zero distances
diagnosable.

The first version can use VTK/PyVista locators already available in the project.
A later implementation may use a dedicated vectorized BVH if profiling shows
that locator construction or queries dominate runtime.

### 3. Estimate material thickness

Nearest-surface distance alone is insufficient near folds because the closest
triangle may lie tangentially on the same interface. A valid thickness sample
must satisfy all of these:

1. The candidate is not incident or part of the same smooth patch.
2. Its owner/material relationship represents a distinct interface.
3. The displacement has a sufficient component along the source normal.
4. A segment between samples does not cross an unrelated interface first.

For ordinary wrapped ViennaPS level sets, a fast path may use the known ordered
interfaces and normal/vertical ray intersections. The general Euclidean BVH
path remains necessary for overhangs, sidewalls, and imported surfaces.

### 4. Estimate curvature

Estimate principal or normal-variation curvature over a small vertex
neighborhood. Convert the allowed chord error `epsilon_geometry` to an edge
bound. A practical approximation for radius `R` is:

```text
h_curvature <= sqrt(8 * R * epsilon_geometry)
```

Noisy curvature estimates must be smoothed and capped by the input grid scale.
The estimator should never refine indefinitely in marching-cubes noise that is
smaller than ViennaLS can resolve.

### 5. Enforce gradation

Abrupt size jumps create poor tetrahedra even when both endpoint sizes are
individually reasonable. Smooth the field over the surface constraint graph so
neighboring desired lengths satisfy a configurable gradation bound, initially:

```text
h_large / h_small <= 1.3 to 1.5 per edge neighborhood
```

Small sizes propagate only far enough to form a transition zone; they must not
force the entire domain to the minimum size.

## Proposed Data Model

Keep estimation separate from mesher-specific serialization:

```python
@dataclass(frozen=True)
class SizingSample3D:
    point: Point3D
    edge_length: float
    reason: Literal["grid", "thickness", "curvature", "junction", "limit"]
    feature_distance: float | None = None


@dataclass(frozen=True)
class SizingField3D:
    samples: tuple[SizingSample3D, ...]
    minimum: float
    maximum: float
    elements_across_feature: float
    maximum_gradation: float
```

The automatic quality preset produces this type. Surface processing, TetGen input, and
reporting consume it. This avoids coupling the estimator to `.mtr`, `.var`, or
PyMeshLab APIs and makes it testable without external meshers.

Add a `SizingReport3D` to the final result and JSON sidecar containing:

- minimum, median, and maximum requested edge lengths;
- the number of samples limited by each reason;
- the thinnest detected material feature and its material/interface pair;
- clamped samples and why they were clamped;
- gradation adjustments;
- and final surface/volume quality statistics.

## Applying the Field to Surface Processing

The current PyMeshLab decimator accepts a target face count per patch, not a
spatially varying edge-length field. There are three implementation levels.

### Initial implementation: sizing bands

Quantize `h(x)` into a small number of logarithmic bands, for example four to
eight. Split existing ownership patches where the requested band changes, then
allocate each subpatch a target derived from its area and band edge length:

```text
target_faces = ceil(area / (sqrt(3) / 4 * h_band^2))
```

Band boundaries become fixed constraints during decimation. This reuses the
conforming patch infrastructure, but too many bands would create excessive
boundaries and reduce simplification. Gradation smoothing and a deliberately
small band count are therefore required.

### Better implementation: adaptive remeshing

Replace pure edge-collapse decimation with a constrained isotropic remesher that
can split, collapse, and flip edges according to `h(x)`. Shared patches must be
remeshed once and reused by every owner, just as they are decimated once today.
Material junctions, wall traces, and protected seams remain hard constraints.

This produces more regular triangles and can refine an input surface where a
thin feature is under-resolved. It is more work and must not be attempted until
the PLC validity checks can reject flips, overlaps, and changed boundaries
cheaply.

### Safety rule

Local sizing may request more faces than the input has, but the existing
decimator cannot create them. The report must distinguish `requested` from
`representable`. Until adaptive remeshing exists, under-resolved samples are
preserved at input resolution and reported rather than silently claimed as
satisfied.

## Applying the Field to TetGen

Surface control and volume control must use the same characteristic size.
TetGen integration should be staged:

1. Assign stable boundary markers to material interfaces, walls, and bottom.
2. Write a `.var` file for facet maximum-area and constrained-segment
   maximum-length bounds where a piecewise-constant value is sufficient.
3. Write `.mtr` values at PLC vertices and enable TetGen's metric/sizing switch
   for a vertex-sampled isotropic field.
4. If vertex metrics do not adequately control the interior, generate a coarse
   first-pass tetrahedral mesh and use it as a background sizing mesh for a
   second refinement pass.

For desired edge length `h`, use these starting conversions:

```text
maximum boundary triangle area = sqrt(3) / 4 * h^2
target regular tetrahedron volume = h^3 / (6 * sqrt(2))
```

They are scale conversions, not guarantees about TetGen's final element shape.
TetGen quality constraints, PLC segments, and local geometry may force smaller
elements. The final report must compare requested and achieved sizes rather than
assuming the conversion was exact.

Do not use `-Y` as the normal implementation: preventing boundary splitting can
conflict with quality refinement and leave poor tetrahedra. Boundary preservation
is appropriate only when lsmesher has already created a sufficiently regular,
fully sized boundary mesh.

## Automatic Policy Integration

Local-feature sizing fits into the proposed automatic `mesh()` sequence as
follows:

```text
extract live ViennaPS interfaces and material IDs
  -> validate and normalize the conforming surface complex
  -> estimate grid scale, thickness, curvature, and junction distances
  -> build and smooth SizingField3D
  -> apply field to conforming surface processing
  -> close PLC and apply wall/bottom sizing
  -> TetGen with surface and volume sizing
  -> correctness gates and achieved-quality measurement
  -> bounded safer retry when required
```

The retry ladder must retain the same detected features. A recovery attempt may
preserve more surface geometry or relax tetrahedron shape targets, but it must
not increase `h(x)` across a thin material merely to make TetGen succeed.

## Correctness Gates

A locally sized mesh is accepted only when:

- the PLC is conforming and intersection-free;
- every tetrahedron has positive volume;
- every expected ViennaPS material ID occurs in the output;
- no unknown material ID occurs;
- every retained material component has a valid region seed;
- protected seams and material junctions are unchanged;
- thin-feature samples meet the requested elements-across-feature count within
  a documented tolerance, or are explicitly reported as input-limited;
- and boundary and volume size gradation remain within quality limits.

TetGen success alone is not an acceptance criterion.

## Implementation Stages

### Stage 1: estimator and diagnostics

- Add `SizingField3D` and `SizingReport3D` without changing generated meshes.
- Retrieve ViennaLS grid spacing from live domains when available.
- Implement unique-triangle BVH queries, exclusions, thickness samples, and
  reason tagging.
- Visualize the field in the viewer and write it as a diagnostic VTP/JSON.
- Establish measurements on Selective Epitaxy, FinFET, stacked nanowire, and
  thin alternating Si/SiGe layers.

### Stage 2: surface sizing bands

- Smooth and quantize the field.
- Partition ownership patches by band while preserving conformity.
- Reuse the existing area-to-face-count allocation per subpatch.
- Add explicit input-limited reporting.
- Validate the resulting PLC with TetGen intersection checks.

### Stage 3: TetGen boundary sizing

- Add stable facet markers and `.var` output.
- Apply size-consistent walls, bottom, and constraint segments.
- Compare achieved boundary sizes against requested bands.

### Stage 4: volume sizing

- Add `.mtr` vertex metrics.
- Evaluate whether a background mesh/two-pass refinement is required.
- Add achieved volume-edge, volume, dihedral, and aspect-ratio statistics.

### Stage 5: adaptive remeshing

- Introduce constrained split/collapse/flip operations only if sizing bands are
  measurably inadequate.
- Preserve shared patches once, constraints exactly, and all current PLC safety
  fallbacks.

## Test Plan

Unit geometries should have analytic expectations:

- parallel planes separated by `t` request `h <= t / N`;
- coincident shared planes do not create a zero feature size;
- adjacent coplanar triangles do not limit one another;
- a sphere selects a curvature-consistent size;
- a narrow gap refines locally while a distant plane remains coarse;
- gradation smoothing respects its ratio bound;
- repeated ViennaPS materials retain one material ID across separate regions;
- and field results are invariant to input surface ordering.

End-to-end tests should verify:

- at least the quality preset's requested number of elements across thin layers;
- no lost materials or inverted tetrahedra;
- clean TetGen PLC intersection checks;
- fewer tetrahedra than an equivalent globally fine mesh;
- and bounded geometric deviation from the undecimated interfaces.

Record runtime, peak memory, surface faces, tetrahedra, quality percentiles, and
material volumes for every reference case so quality changes are evidence-based.

## Open Decisions

Before implementation, decide:

1. Which ViennaPS API reliably exposes grid spacing for both legacy and
   `d2`/`d3` domains.
2. Whether VTK locators are fast enough for the estimator.
3. Whether sizing-band boundaries introduce unacceptable patch constraints.
4. Whether TetGen `.mtr` is sufficient or a background mesh is necessary.
5. The balanced/accurate elements-across-feature and gradation thresholds.
6. The geometric-error metric used to compare the final boundary with the
   original ViennaLS interfaces.
7. Runtime and tetrahedron-count ceilings for automatic mode.

Do not begin adaptive remeshing until Stages 1 through 3 demonstrate that the
simpler banded approach cannot meet fidelity and mesh-size goals.
