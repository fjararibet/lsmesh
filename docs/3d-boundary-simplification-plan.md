# Plan: Collinear Simplification of 3D Boundary Curves

Status: **attempted and reverted** — the approach is sound and measurably
effective, but it exposed a decimation robustness problem that needs to be
solved first. This note records the design, what was implemented, the exact
failure modes found, and the remaining TODO so the work can be resumed.

## Motivation

Patch decimation (`decimate_3d_patch`) never touches patch boundaries, so the
material junction curves and wall traces keep full marching-cubes resolution
and bound the minimum mesh size. The 2D pipeline already removes collinear
points (`geometry_2d.remove_collinear`, driven by `--epsilon`); the 3D
boundary curves deserve the same treatment.

Measured potential on `viewer_presets/selectiveEpitaxy` with `epsilon=1e-6`:
constraint network shrinks from **1012 points / 1020 edges to 176 points /
184 edges** (–83%). Long exactly-straight runs exist because crystal facets
and mask planes are planar, so their junction lines are straight.

## Design (implemented, then reverted)

All of this lived in `pipeline_3d.py`; recover it from this description or
from the reflog around commit `bb82cbc` (it was stashed on top of it once).

1. `_face_owners(surfaces)` — already exists (used by `_patch_groups`).
2. `_constraint_graph(surfaces)` — build the coordinate-keyed graph of
   constraint edges: an edge is constraint when its adjacent (deduplicated)
   faces number != 2 or have different owner sets. These are exactly the
   curves patch decimation freezes.
3. `simplify_3d_boundaries(surfaces, *, epsilon)` — iteratively collapse any
   graph point with exactly two neighbors that lies within `epsilon` of the
   segment between them (point-to-segment distance; the 3D analogue of the
   2D triangle-area test). Junction points (degree >= 3) are never touched.
   Collapses are recorded as a coordinate remap and applied to every surface
   (`_collapse_surface_points`): face vertices are remapped through the
   resolved chain, consecutive duplicates dropped, faces with fewer than
   three unique vertices dropped. Because the remap is by coordinate, the
   conformity of shared regions survives.
4. Wiring: `build_3d_surface(..., epsilon=...)` ran simplification before
   patch decimation; the CLI passed `args.epsilon`; the viewer sidebar label
   became "Collinear epsilon exponent" (it already plumbed epsilon through).

Verification done: with simplification but **without** decimation, the merged
complex closed fine and `tetgen -d` accepted it ("The input surface mesh is
correct"), confirming the collapse itself is geometry-safe and crack-free.

## Failure Modes Found (with decimation enabled)

Both failures appear only when patch decimation runs *after* simplification:
sparse boundaries mean PyMeshLab is much less constrained near patch borders.

1. **Patch fold-over.** PyMeshLab produced duplicate faces (same vertex set
   twice) inside a single decimated patch along long boundary edges. The
   merge step deduplicates faces, so one copy was dropped and the complex was
   torn open — symptom: `close_3d_surface` rejected an interior
   "boundary edge ... does not lie on a bounding box side wall".
   *Fix implemented:* `_decimation_is_valid` — reject a decimated patch
   unless boundary edge set is unchanged, no face appears twice, and every
   edge has multiplicity <= 2; retry with doubled target, fall back to the
   undecimated patch. This worked.

2. **Coplanar neighbor overlap.** With fold rejection in place, `tetgen -d`
   reported ~93 "two segments exactly intersect" pairs, mostly in the z=3
   mask-top plane. Diagnosis: crossing segment endpoints did not exist in
   the original constraint network, so decimation created them. The patches
   `{1}` (mask top under the crystal) and `{1,2}` (mask top outside it) are
   coplanar neighbors separated by the simplified rim; in-plane triangle
   inversions during collapse let one patch bulge across the concave rim
   into the other — coplanar overlapping facets.
   *Fix attempted but not validated:* `preservenormal=True` in
   `meshing_decimation_quadric_edge_collapse` (inversion is exactly a normal
   flip for planar patches). The run was interrupted after ~5 minutes — the
   validity-retry loop re-decimates large patches many times when targets
   are rejected, which is far too slow even if it converges.

## TODO to resume this work

- [ ] Re-apply the design above (steps 1-4) plus `_decimation_is_valid`.
- [ ] Add `preservenormal=True` and first check it actually prevents the
      coplanar overlap on the selectiveEpitaxy preset at default targets,
      *without* the retry loop masking it (test `decimate_3d_patch` per
      patch and `tetgen -d` the merged result directly).
- [ ] Fix the retry-loop cost regardless: cap retries (e.g. 3 doublings),
      log/propagate when a patch falls back undecimated, and consider
      validating cheaply per collapse instead of per full decimation pass.
- [ ] If `preservenormal` is insufficient: add an explicit in-plane
      inversion check (compare each decimated face normal against the
      patch's dominant normal; reject sign flips) in `_decimation_is_valid`,
      or detect coplanar patch-pair overlap directly.
- [ ] Alternative mitigation if robustness stays hard: cap the length of
      simplified boundary segments (split long straight runs at a multiple
      of the local mesh size) so border triangles cannot span concave
      sections — keeps most of the point reduction with far less risk.
- [ ] Re-add tests: strip-surface collapse to its 4 corners with area
      preserved; junction points (degree 3) never removed on the
      strip+two-bump pair; end-to-end selectiveEpitaxy `tetgen -d` clean
      with decimation on and off; regenerate
      `tests/end_to_end/expected/3d_out.off`.
- [ ] Update `3d-surface-merge-method.md` (pipeline order becomes
      simplify -> decimate -> merge -> close) and the viewer epsilon label
      ("Collinear epsilon exponent", applies to 2D and 3D).

## Reproduction shortcuts

- Constraint-network measurement: build surfaces, call
  `_constraint_graph(surfaces)` before/after `simplify_3d_boundaries`.
- Overlap diagnosis: run `tetgen -d` on the generated `.poly`, regex the
  intersecting segment ids, map them to coordinates via the node section,
  and check whether the endpoints exist in the pre-simplification
  constraint graph — if not, decimation invented them.
