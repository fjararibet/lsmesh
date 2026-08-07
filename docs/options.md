# Lower-level options

Pass `MeshOptions` when you need exact control over boundary construction and
the external mesher:

```python
options = lsmesh.MeshOptions(
    build=lsmesh.BuildOptions(...),
    mesher=lsmesh.MesherOptions(...),
    run_mesher=True,
    validate=True,
)

result = lsmesh.mesh(domain, options=options)
```

`MeshOptions` is the package-root name for `MeshingOptions`. Supplying it
disables automatic quality-derived sizing and recovery: lsmesh makes exactly
one attempt with the values provided. It still computes the final quality
report unless meshing is disabled.

## BuildOptions

`BuildOptions` controls conversion from level-set interfaces to mesher-ready
boundary geometry:

```python
build = lsmesh.BuildOptions(
    epsilon=1e-6,
    detect_holes=True,
    bottom_margin=0.10,
    seam_protection_rings=8,
    random_seed=42,
    decimation=lsmesh.DecimationOptions3D(...),
)
```

| Field | Default | Purpose |
| --- | ---: | --- |
| `epsilon` | `1e-6` | Tolerance used while simplifying and merging geometry. |
| `detect_holes` | `True` | Generate 2D material-region seeds between interfaces. |
| `bottom_margin` | `0.10` | Relative margin used to close open 3D interfaces below the geometry. |
| `seam_protection_rings` | `8` | Face rings protected around material seams during 3D decimation. |
| `random_seed` | `None` | Makes fallback 2D region sampling repeatable. |
| `decimation` | defaults below | Controls 3D surface simplification. |

`bottom_margin`, `seam_protection_rings`, and `decimation` affect the 3D
pipeline. `detect_holes` and `random_seed` affect the 2D pipeline.

## DecimationOptions3D

```python
decimation = lsmesh.DecimationOptions3D(
    enabled=True,
    target_total_faces=None,
    target_edge_length=0.5,
    target_faces=None,
    quality_threshold=0.3,
    preserve_boundary=True,
    boundary_weight=1000.0,
    optimal_placement=False,
    planar_quadric=True,
    planar_weight=0.001,
)
```

The target fields select how much of the extracted 3D interface is retained:

- `target_edge_length` derives the face budget from a physical edge length.
- `target_total_faces` sets a shared budget for all unique decimatable patches.
- `target_faces` is a direct per-surface fallback target.
- leaving all targets as `None` uses the library's default total-face budget.

`preserve_boundary=True` should normally remain enabled. It fixes patch
boundaries so adjacent material surfaces remain conforming. Disabling it allows
boundaries to move and makes `boundary_weight` relevant, but can create holes
at material interfaces.

Set `enabled=False` to pass the extracted interface triangulation through
without decimation:

```python
lsmesh.DecimationOptions3D(enabled=False)
```

This preserves the most input detail but can substantially increase memory use
and TetGen runtime.

## MesherOptions

`MesherOptions` controls Triangle and TetGen:

```python
mesher = lsmesh.MesherOptions(
    triangle_min_angle=20.0,
    tetgen_quality_ratio=1.5,
    tetgen_min_dihedral=10.0,
    tetgen_max_volume=0.25,
)
```

| Field | Default | Used by | Purpose |
| --- | ---: | --- | --- |
| `triangle_min_angle` | `20.0` | Triangle | Minimum requested 2D triangle angle in degrees. |
| `tetgen_quality_ratio` | `2.0` | TetGen | Maximum tetrahedron radius-edge ratio; smaller is stricter. |
| `tetgen_min_dihedral` | `0.0` | TetGen | Optional minimum dihedral angle in degrees. |
| `tetgen_max_volume` | `None` | TetGen | Optional maximum tetrahedron volume in model units cubed. |

Stricter values can improve element shape or resolution, but they may greatly
increase element count or make difficult geometries impossible to tetrahedralize.

## Pipeline controls

`MeshOptions` also has two Boolean controls:

- `validate=True` validates constructed geometry before invoking the mesher.
- `run_mesher=True` runs Triangle or TetGen after boundary construction.

Keeping validation enabled is strongly recommended. Disable meshing to inspect
or export only the intermediate boundary:

```python
options = lsmesh.MeshOptions(run_mesher=False)
result = lsmesh.mesh(domain, options=options)

lsmesh.write(result.geometry, "boundary.vtp")
```

When an output path is passed with `run_mesher=False`, use a boundary format:
`.poly` or `.vtp` for 2D, and `.poly`, `.off`, or `.vtp` for 3D.

## Complete example

```python
import lsmesh

options = lsmesh.MeshOptions(
    build=lsmesh.BuildOptions(
        epsilon=1e-6,
        bottom_margin=0.15,
        seam_protection_rings=12,
        decimation=lsmesh.DecimationOptions3D(
            target_edge_length=0.5,
            preserve_boundary=True,
        ),
    ),
    mesher=lsmesh.MesherOptions(
        tetgen_quality_ratio=1.5,
        tetgen_min_dihedral=5.0,
        tetgen_max_volume=0.25,
    ),
)

result = lsmesh.mesh(domain, "device.vtu", options=options)

print(result.validation)
print(result.quality)
```

Start with one change at a time. In particular, set a physical
`target_edge_length` before tightening TetGen quality and volume constraints;
otherwise it is difficult to tell whether failures originate in surface
construction or volume meshing.
