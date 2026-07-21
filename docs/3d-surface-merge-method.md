# 3D Surface Merge Method

This note documents the current 3D surface merge approach used in
`src/lsmesher/pipeline_3d.py`.

## Goal

The merge step combines multiple 3D interface surfaces into one piecewise
linear complex (PLC) that TetGen accepts as `.poly` input and meshes into
material-tagged tetrahedra.

## Key Insight: Inputs Already Conform

ViennaPS extracts each material interface from wrapped level sets on a shared
grid. Where two adjacent interfaces coincide (for example, the mask surface
over regions where nothing grew), they contain **bitwise-identical vertices
and faces**. For `viewer_presets/selectiveEpitaxy`:

- interfaces 0 and 1 share 5000 identical faces
- interfaces 1 and 2 share 4600 identical faces

This is the same property the 2D pipeline exploits in `merge_polygons`
(point deduplication makes coincident segments shared).

## Why Earlier Approaches Failed

Earlier 3D pipelines decimated each surface independently
(`decimate_3d_surface`, ~100 faces, `preserveboundary=False`) and then tried
to stitch boundary loops between adjacent surfaces. Independent decimation
re-triangulates the coincident regions differently per surface, so the merged
result contained *almost*-identical overlapping geometry. TetGen rejected it
with:

- two line segments are exactly overlapping
- a vertex lies exactly on a line segment
- two segments exactly intersect

No stitching strategy can fix this, because the overlap is created before
merging. Decimation must not run before the merge.

## Current Approach

### 0. Conforming Patch Decimation (`decimate_conforming_3d_surfaces`)

Decimation cannot run per surface, but it can run per *patch*. The input
surfaces are partitioned into patches: maximal edge-connected groups of faces
owned by the same set of surfaces (for `selectiveEpitaxy`: unique-to-0,
shared-0-1, unique-to-1, shared-1-2, unique-to-2). Patch borders are exactly
the material-junction curves and wall traces.

Each patch is decimated once (`decimate_3d_patch`, PyMeshLab quadric edge
collapse with `preserveboundary=True`, subset placement) and every surface is
rebuilt from its decimated patches. Because the shared patch instance is
reused by both surfaces and patch boundaries are kept exactly fixed, the
rebuilt surfaces still conform bitwise where they coincide.

`decimate_3d_patch` verifies after decimation that the patch boundary edge
set is unchanged; if PyMeshLab altered it, the face target is relaxed and the
decimation retried, falling back to the undecimated patch. Patches at or
below the face target are left untouched.

Decimation is tunable through `DecimationOptions3D` (enable/disable, target
faces per patch, quality threshold, boundary weight, optimal placement,
planar quadric and its weight). The options are exposed as `--decimate-*`
CLI flags (`--no-decimate` to skip) and as sidebar controls in the Streamlit
viewer for 3D presets; the viewer caches outputs per option combination.
Boundary preservation is not tunable — conformity depends on it.

### 1. Merge by Deduplication (`merge_3d_surfaces`)

1. Sort surfaces by minimum `z` (wrapped level sets stack bottom-up).
2. Concatenate all points and faces.
3. Deduplicate coincident points (rounded to 9 decimals).
4. Drop duplicate faces, keeping one copy.

The kept copy of each shared face becomes an internal facet of the PLC.
Edges where a shared region meets two unique regions have multiplicity 3,
which is valid PLC topology. Running `tetgen -d` on the merged complex
confirms: "The input surface mesh is correct."

### 2. Close the Volume (`close_3d_surface`)

The merged complex is open at the simulation domain sides. All boundary
edges (edges used by exactly one face) lie exactly on the four vertical
planes of the XY bounding box; `close_3d_surface` raises if one does not.

Closure adds five TetGen facets:

- One facet per side wall, built from polygons in TetGen's multi-polygon
  facet syntax: every boundary edge on that wall as a two-vertex polygon
  (segment), the vertical corner columns subdivided at every interface
  trace endpoint, and a bottom edge. TetGen triangulates each wall facet
  itself; the interface traces act as constraint segments inside it.
- One rectangular bottom facet at `min_z - 0.10 * height`.

These facets are stored in `Surface3D.facets` and serialized by
`vtp_to_poly_string`; the surface faces stay ordinary one-polygon facets.

### 3. Sample Material Regions (`collect_3d_regions`)

See `3d-material-regions.md` for details. One region point is sampled per
edge-connected component of each layer's unique faces, so disconnected
volumes of the same material (for example, a mask split in two by a fin) all
receive the layer's material ID.

### 4. TetGen Invocation

The CLI runs `tetgen -pAkF mesh.poly`. The `-A` flag is required for TetGen
to apply the region attributes from the `.poly` region section.

## Observed SelectiveEpitaxy Result

For `viewer_presets/selectiveEpitaxy` (three interfaces, 31000 facets
before decimation), TetGen succeeds with no warnings. With patch decimation
the complex shrinks to 1420 surface facets and TetGen produces 3866
tetrahedra across the three materials (substrate, two-component mask,
epitaxy). Without decimation the same pipeline yields 63761 tetrahedra.
`tetgen -d` confirms the decimated complex stays intersection-free.

## Limitations

- Input surfaces must conform exactly where they coincide. Geometry from
  different grids, or externally decimated/remeshed inputs, will not merge
  correctly.
- All boundary edges must lie exactly on the XY bounding box side walls.
- Patch boundaries (junction curves and wall traces) are never decimated, so
  they keep the input resolution.
- Patch decimation moves only interior vertices (subset placement), which
  keeps cross-patch intersections unlikely but not formally impossible; very
  thin layers combined with aggressive targets could still self-intersect,
  and TetGen will report it.
