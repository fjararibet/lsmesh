# 3D Material Regions

This note documents how 3D material IDs are propagated through the current
TetGen path.

## Goal

The 2D pipeline assigns material regions by writing region attribute points into
Triangle `.poly` input. The 3D pipeline now follows the same idea using TetGen
region records.

Each material region is represented by one interior `Point3D` plus a material ID.
TetGen uses those points to assign attributes to generated tetrahedra.

## Data Flow

### 1. Surface Carries Region Points

`Surface3D` now includes:

```python
regions: tuple[Region3D, ...] = ()
```

Each `Region3D` pairs an interior sample point with an explicit material ID.
The regions are carried with the merged surface until `.poly` serialization.

### 2. Region Point Sampling

`collect_3d_regions` samples regions from the sorted input surfaces (called
by `merge_3d_surfaces` before deduplication).

Layer `i` is the material volume between surface `i - 1` (or the closure
bottom plane for the first layer) and surface `i`, and gets material ID
`i + 1`. Because wrapped level sets coincide wherever a layer has zero
thickness, the faces *unique* to surface `i` (not coincident with surface
`i - 1`) cap exactly the regions where the material exists.

For each edge-connected component of those unique faces:

1. Candidate faces are visited in descending XY-projected area.
2. A vertical ray is cast down from the face centroid against both bounding
   surfaces; the nearest crossing below (or the bottom plane) is found.
3. The midpoint of that crossing-free gap is the region point, which is
   therefore strictly inside the material volume.

Sampling one point per component matters: in `selectiveEpitaxy` the mask is
split into two disconnected halves by the fin, and each half needs its own
region point carrying the same material ID.

### 3. TetGen POLY Region Records

`surface_3d_to_poly_text` passes `surface.regions` to the 3D POLY writer.

The writer emits TetGen region records in this form:

```text
<region-count>
<id> <x> <y> <z> <material-id> <max-volume>
```

Example:

```text
2
1 0.5 0.5 0.5 1 -1
2 2.5 0.5 0.5 1 -1
```

The final `-1` means no maximum volume constraint is requested for that region.

### 4. TetGen Invocation

The CLI runs TetGen with:

```text
tetgen -pAkF mesh.poly
```

The `-A` flag makes TetGen apply the region attributes; without it the
region records in the `.poly` file are ignored. The `.node` and `.ele` files
are not suppressed because they are needed to read tetrahedra and their
material attributes after TetGen finishes.

### 5. Reading TetGen Output

After successful TetGen execution, the CLI reads:

```text
mesh.1.node
mesh.1.ele
```

The `.node` file provides generated 3D vertices.

The `.ele` file provides tetrahedra. When TetGen writes region attributes, the
attribute is read from the element line and stored as the tetrahedron material
ID.

### 6. Writing VTU With Materials

The generated tetrahedral mesh is written to:

```text
mesh.1.vtu
```

The VTU writer stores tetrahedra as `VTK_TETRA` cells and writes material IDs as
cell data named:

```text
Material
```

This mirrors the 2D path, where Triangle attributes are written as cell data on
the output VTU.

## Streamlit Viewer Behavior

When 3D external meshing is enabled, the viewer now prefers the attributed VTU
output:

```text
mesh.1.vtu
```

If no VTU exists, it falls back to TetGen's VTK output if present:

```text
mesh.1.vtk
```

If TetGen fails, the captured TetGen stdout/stderr is raised as an exception and
shown in Streamlit.

## Limitations

The vertical-ray sampling assumes each material volume component is capped
from above by faces unique to its upper surface, which holds for wrapped
level sets extracted from a shared grid. It may still fail when:

- input surfaces do not conform exactly where they coincide (for example,
  after independent decimation or remeshing)
- a component's faces are all nearly vertical, leaving no usable ray origin
- a material volume component is thinner than the sampling tolerance
  everywhere
