# 3D Decimation Patching

The 3D pipeline decimates surfaces patch by patch instead of decimating each
input interface independently. The goal is to reduce triangle count without
breaking the conforming surface complex that is later written for TetGen.

## Why Patches Are Needed

The input surfaces often share coincident regions. For example, two material
interfaces can contain the same polygonal face where their boundaries touch.
If each surface is decimated independently, the decimator may move or remove
different vertices on each copy of that shared region. The two surfaces would
then no longer match exactly.

That mismatch is dangerous for TetGen because the `.poly` file represents a
piecewise-linear complex. Coincident material boundaries must use identical
geometry. Small gaps, overlaps, T-junctions, or differently triangulated copies
can produce invalid facets or ambiguous volumes.

## Patch Definition

Patch construction happens in `src/lsmesher/pipeline_3d.py`:

- `_patch_groups(...)`
- `_connected_keys(...)`
- `decimate_conforming_3d_surfaces(...)`

Each input face is converted to a coordinate-based key with `_face_key(...)`.
The key is independent of face orientation and point indices, so coincident
faces from different surfaces are recognized as the same geometric face.

For every unique face key, the pipeline records the set of input surfaces that
own that face. This owner set is the patch label. A patch is then a maximal
edge-connected group of faces with the same owner set.

In other words:

```text
patch = connected faces that belong to exactly the same surfaces
```

This splits the geometry along material junction curves and along the boundary
between shared and non-shared regions.

## Decimation Flow

The high-level flow is:

```text
input surfaces
  -> group coincident/connected faces into patches
  -> decimate each patch once
  -> copy the decimated patch back into every owning surface
  -> merge surfaces
  -> close the domain
  -> write TetGen POLY
```

`decimate_conforming_3d_surfaces(...)` owns the rebuild step. It creates one
surface builder per original input surface. For each patch, it runs the patch
decimator once, then inserts the exact same decimated faces into every surface
listed in the patch owner set.

Because shared patches are decimated once and reused, coincident regions remain
bitwise identical after decimation.

## Boundary Preservation

Patch boundaries are not optional. They represent either:

- the edge of the original input surface,
- the curve where ownership changes between patches,
- or a material junction that adjacent patches must share.

`decimate_3d_patch(...)` therefore treats patch boundaries as fixed. It first
triangulates polygonal faces with `_triangulate_faces(...)`, then calls
PyMeshLab quadric edge-collapse decimation through `_decimate_patch_once(...)`
with:

```python
preserveboundary=True
boundaryweight=options.boundary_weight
```

After decimation, the pipeline recomputes boundary edge coordinate keys with
`_boundary_edge_keys(...)`. The decimated patch is accepted only if its boundary
edge set exactly matches the original patch boundary.

If the requested target is too aggressive and PyMeshLab changes the boundary,
the target face count is relaxed by doubling it. If no boundary-preserving
result is found before reaching the original face count, the original patch is
kept.

This means decimation is conservative: preserving a valid conforming complex is
more important than hitting the requested triangle count.

## Decimation Targets

Patch targets are derived from either a global face budget or a target edge
length. Both modes scale with physical patch area; patches do not receive an
identical fixed face count. See [3D decimation targets](3d-decimation-targets.md)
for the allocation algorithm, safety floors, reports, and migration from the
deprecated per-patch option.

## Merge And Closure After Decimation

After patch-wise decimation, `build_3d_surface(...)` calls:

```python
merge_3d_surfaces(...)
close_3d_surface(...)
```

Merging deduplicates coincident geometry using coordinate keys. Closure then
adds the outside walls and bottom facets needed to turn the stack of interfaces
into a closed volume suitable for TetGen.

The patching step must happen before this merge/closure stage. Once the
surfaces are merged, the pipeline loses the per-input ownership information
needed to know which regions must remain identical across which surfaces.

## Failure Modes This Avoids

Patch-wise decimation is designed to avoid:

- non-matching triangulations on coincident material boundaries,
- cracks between surfaces that used to share faces,
- moved material junction curves,
- open seams after merging,
- and TetGen failures caused by invalid or non-conforming facets.

It does not guarantee every generated geometry will be accepted by TetGen.
TetGen can still fail if the source geometry contains self-intersections,
zero-volume regions, duplicated incompatible facets, or region points that do
not land inside the intended material volumes. The decimation patching only
ensures that decimation itself does not introduce non-conforming shared
surfaces.
