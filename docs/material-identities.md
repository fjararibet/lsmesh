# Material Identities

When meshing a live ViennaPS domain, lsmesher reads the material map associated
with its level sets. The final Triangle or TetGen mesh uses those ViennaPS IDs
as its `Material` cell-data values. Disconnected volumes and repeated level sets
with the same ViennaPS material therefore receive the same final value.

## External Mesher Encoding

ViennaPS material IDs are application identifiers and may include `0`. TetGen
does not safely preserve `0` as a region attribute: it treats it as unassigned
and may generate a different attribute for each disconnected region. Passing a
Bosch-process mask through directly, for example, turned repeated material `0`
into unrelated attributes `11` and `12`.

lsmesher avoids giving application IDs directly to Triangle or TetGen. For each
mesher invocation it creates a temporary positive, consecutive encoding:

```text
Si region,   ViennaPS material 10 -> mesher attribute 1
Mask region, ViennaPS material  0 -> mesher attribute 2
Mask region, ViennaPS material  0 -> mesher attribute 3
```

Each disconnected region seed receives a unique temporary value because TetGen
expects region attributes to identify regions independently. Multiple temporary
values may therefore map back to the same application material. Immediately
after reading the external mesher output, lsmesher decodes every element
attribute back to the original application ID. The temporary encoding exists
only in the private `.poly` and mesher output files inside the invocation's
temporary directory.

Consequently:

- `result.materials` describes the original ViennaPS material map;
- `result.mesh.attributes` contains original ViennaPS IDs;
- the final VTU `Material` cell-data array contains original ViennaPS IDs;
- quality and material-coverage checks operate on original ViennaPS IDs; and
- an unexpected attribute produced by an external mesher is rejected rather
  than silently exposed as a new material.

For inputs without a ViennaPS material map, explicitly supplied geometry region
IDs receive the same reversible treatment. Existing implicit 2D region numbers
remain the public result when no IDs were supplied.

## Nested ViennaPS Interfaces

ViennaPS level sets are nested and a material region is not necessarily below
the corresponding local surface. For upper layers, lsmesher samples between a
component and the nearest separated crossing of the preceding interface in
either vertical direction. This matters for structures such as the Bosch mask:
sampling downward unconditionally can place both mask seeds inside silicon,
causing TetGen to regard the actual mask volumes as unmarked regions.

The generated mesh is still checked after decoding. Every material from the
ViennaPS map must be present, and attributes that cannot be traced through the
temporary encoding are rejected.
