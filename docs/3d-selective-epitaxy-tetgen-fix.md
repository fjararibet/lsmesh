# Making the 3D SelectiveEpitaxy Preset Mesh With TetGen

This note records the investigation and changes that made
`viewer_presets/selectiveEpitaxy` (3D) pass through TetGen, including the
reintroduction of decimation. Companion notes:

- `3d-surface-merge-method.md` — the resulting merge/closure method
- `3d-material-regions.md` — the resulting material region sampling

## Symptom

No merge strategy produced a `.poly` that TetGen accepted. TetGen always
aborted during boundary recovery with diagnostics like:

```text
Warning:  Two line segments are exactly overlapping.
Warning:  A vertex lies exactly on a line segment.
Warning:  Two segments exactly intersect.
```

## Root Cause

It was never the merge step. The ViennaPS interfaces are extracted from
wrapped level sets on a shared grid, so where two surfaces coincide they are
**bitwise identical** (interfaces 0/1 share 5000 identical faces, 1/2 share
4600). The pipeline decimated each surface *independently* before merging
(`targetfacenum=100`, `preserveboundary=False`), which re-triangulated the
coincident regions differently per surface. Every merge of the decimated
surfaces therefore contained almost-coincident overlapping geometry — exactly
the overlaps TetGen reported. Boundary-loop stitching on top of that could
never repair it.

Proof: concatenating the *raw* surfaces, deduplicating points, and dropping
duplicate faces yields a complex for which `tetgen -d` reports
"The input surface mesh is correct."

## Changes

### Pipeline (`src/lsmesher/pipeline_3d.py`)

1. **Merge** (`merge_3d_surfaces`): replaced boundary-loop stitching with
   point deduplication plus duplicate-face dropping (the 2D
   `merge_polygons` idea lifted to 3D). The single kept copy of each shared
   face becomes an internal material-interface facet of the PLC.
2. **Closure** (`close_3d_surface`, new): all open boundary edges lie
   exactly on the four XY bounding-box side planes. Each wall becomes one
   TetGen multi-polygon facet (boundary edges as segments, subdivided
   vertical corner columns, bottom edge); a rectangular bottom facet at
   `min_z - 0.10 * height` seals the volume. Stored in the new
   `Surface3D.facets` field.
3. **Region sampling** (`collect_3d_regions`, new): one region point per
   edge-connected component of each layer's unique faces, placed by casting
   a vertical ray down from a face centroid and taking the midpoint of the
   crossing-free gap. This fixes the mask, which the fin splits into two
   disconnected volumes — previously one half silently received a spurious
   extra material ID. New `Region3D` type pairs the point with an explicit
   material ID.
4. **Conforming decimation** (`decimate_conforming_3d_surfaces` +
   `decimate_3d_patch`, new; replaces the old per-surface decimation):
   surfaces are partitioned into patches (maximal edge-connected face groups
   owned by the same set of surfaces; patch borders are the junction curves
   and wall traces). Each patch is decimated once with PyMeshLab
   (`preserveboundary=True`, `boundaryweight=1000`, subset placement), the
   boundary edge set is verified unchanged afterwards (with target back-off
   and fallback to the undecimated patch), and each surface is rebuilt from
   its patches. Shared patches are reused by both layers, so conformity
   survives decimation.
5. `build_3d_surface` chains decimate → merge → close; the patch decimator
   is injectable for tests.

### Serialization and CLI

- `vtp_to_poly_string` gained a `facets` parameter for multi-polygon facets
  and writes `Region3D` material IDs into region records
  (`src/lsmesher/polygon_io_3d.py`).
- TetGen is invoked with `-pAkF` instead of `-pkF`; without `-A` the region
  records were silently ignored, so 3D materials never actually worked
  (`src/lsmesher/cli.py`).
- The 3D VTU writer now names its cell array `Material` (capital M) to match
  the 2D writer; the Streamlit viewer only colormaps an array named
  `Material`, so 3D meshes previously rendered uncolored.

### Tests and fixtures

- `tests/test_pipeline_3d.py` rewritten for the new merge/closure/regions/
  decimation behavior (patch-once decimation, boundary preservation under
  real PyMeshLab decimation, off-wall boundary rejection, facet and region
  serialization).
- `tests/end_to_end/expected/3d_out.off` regenerated (the old file was
  produced by the broken per-surface decimation pipeline).

## Verified Result

`lsmesher mesh viewer_presets/selectiveEpitaxy/interface_{0,1,2}.vtp -o mesh.vtp`:

| | facets in | tets out | materials |
|---|---|---|---|
| without decimation | 31000 | 63761 | 3 |
| with patch decimation | 1420 | 3866 | 3 |

Material volumes (decimated vs raw): substrate 2284/2614, mask 1402/1404,
epitaxy 1656/2039. The mask volume is essentially exact; substrate and
epitaxy lose ~12% to geometric smoothing of curved ridges, inherent to
decimation with subset placement. `tetgen -d` confirms both complexes are
intersection-free, and the meshed VTU renders with per-material coloring in
the Streamlit viewer.

## Known Trade-offs

- Junction curves and wall traces are never decimated, so they keep input
  resolution and bound the minimum mesh size. A future improvement is
  constrained simplification of those shared polylines before patch
  decimation.
- Patch decimation moves only interior vertices, making cross-patch
  intersections unlikely but not impossible for very thin layers with
  aggressive targets; TetGen reports them loudly if they occur.
- The whole approach requires inputs that conform exactly where they
  coincide (wrapped level sets from one grid). Externally remeshed inputs
  will not merge.
