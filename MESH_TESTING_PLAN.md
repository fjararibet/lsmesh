# Mesh Validation and Testing Plan
## For ViennaPS Level-Set to Mesh Conversion Pipeline

**Purpose:** Validate that generated meshes are suitable for simulation without implementing full TCAD device simulation

**Scope:** Lightweight validation tests using existing open-source tools

---

## Overview

Since full device simulation (solving drift-diffusion equations) is not the focus of this thesis, we propose lightweight validation tests that:
1. **Verify mesh quality** meets FEM requirements
2. **Test mesh validity** (no self-intersections, proper connectivity)
3. **Perform simple physics solves** (Poisson equation) as sanity checks
4. **Visualize results** to catch obvious issues

---

## Testing Framework

### Option 1: Python-Only Stack (Recommended - Easiest)

**Tools:**
- **meshplex** - Compute mesh quality metrics (angles, aspect ratios, Delaunay violations)
- **PyVista** - Visualization and mesh analysis  
- **FEniCSx** (or legacy FEniCS) - Simple FEM solves
- **NumPy/SciPy** - Matrix validation

**Installation:**
```bash
pip install meshplex pyvista fenics-dolfinx
```

**Advantages:**
- Pure Python ecosystem
- Well-documented
- Can use existing thesis Python code
- Good visualization

**Disadvantages:**
- FEniCSx can be tricky to install (use conda: `conda install -c conda-forge fenics-dolfinx`)

---

### Option 2: Gmsh + GetDP (Alternative)

**Tools:**
- **Gmsh** - Mesh import, simple solver, visualization
- **GetDP** - Finite element solver (bundled with Gmsh in ONELAB)

**Installation:**
```bash
pip install gmsh
```

**Advantages:**
- Native support for Triangle (.node/.ele/.poly) and TetGen (.node/.ele) formats
- Built-in solvers (no additional dependencies)
- Professional visualization
- Industry standard in TCAD

**Disadvantages:**
- Requires learning Gmsh scripting language (.geo files)
- Less flexible than Python

---

### Option 3: MFEM Lightweight (For 3D)

**Tools:**
- **PyMFEM** - Python bindings for MFEM
- **GLVis** - Visualization (comes with MFEM)

**Installation:**
```bash
pip install pymfem
```

**Advantages:**
- High-performance
- Good for complex 3D
- Used by LLNL for production TCAD

**Disadvantages:**
- Steeper learning curve
- Overkill for simple validation

---

## Proposed Test Suite

### Test 1: Mesh Quality Metrics (Mandatory)

**Purpose:** Verify mesh meets basic FEM quality requirements

**Implementation (meshplex):**
```python
import meshplex
import numpy as np

def validate_mesh_quality(mesh_file):
    """Test mesh quality using meshplex"""
    mesh = meshplex.read(mesh_file)
    
    # Element quality (radius ratio)
    quality = mesh.q_radius_ratio
    print(f"Quality metrics:")
    print(f"  Min: {np.min(quality):.4f}")
    print(f"  Mean: {np.mean(quality):.4f}")
    print(f"  Elements with q < 0.1: {np.sum(quality < 0.1)}")
    
    # Check angles (2D triangles)
    if hasattr(mesh, 'angles'):
        angles = mesh.angles
        print(f"Min angle: {np.min(angles):.2f} degrees")
        print(f"Angles < 15 degrees: {np.sum(angles < 15)}")
    
    # Delaunay violations
    if hasattr(mesh, 'num_delaunay_violations'):
        print(f"Delaunay violations: {mesh.num_delaunay_violations}")
    
    # Pass/Fail criteria
    passed = (
        np.min(quality) > 0.01 and
        np.sum(quality < 0.1) < len(quality) * 0.05
    )
    
    if hasattr(mesh, 'angles'):
        passed = passed and np.min(angles) > 5
    
    return passed
```

**Expected Results:**
- Minimum quality > 0.01 (no degenerate elements)
- >95% elements with quality > 0.1
- Minimum angle > 5 degrees (ideally > 15)
- Zero or few Delaunay violations

---

### Test 2: Simple Poisson Equation (Sanity Check)

**Purpose:** Verify mesh can be used for basic FEM solves

**Physics:** Solve Laplacian(u) = f with Dirichlet boundary conditions

**Implementation (FEniCSx):**
```python
from dolfinx import mesh, fem
from dolfinx.fem.petsc import LinearProblem
import numpy as np
import ufl

def test_poisson_solve(mesh):
    """Solve simple Poisson equation as sanity check"""
    V = fem.functionspace(mesh, ("Lagrange", 1))
    
    # Boundary condition: u = 0 on boundary
    facets = mesh.locate_entities_boundary(
        mesh, dim=1,
        marker=lambda x: np.isclose(x[0], 0.0) | np.isclose(x[0], 1.0)
    )
    dofs = fem.locate_dofs_topological(V=V, entity_dim=1, entities=facets)
    bc = fem.dirichletbc(value=0.0, dofs=dofs, V=V)
    
    # Define variational problem
    u = ufl.TrialFunction(V)
    v = ufl.TestFunction(V)
    f = fem.Constant(mesh, -6.0)
    a = ufl.dot(ufl.grad(u), ufl.grad(v)) * ufl.dx
    L = f * v * ufl.dx
    
    # Solve
    problem = LinearProblem(a, L, bcs=[bc])
    uh = problem.solve()
    
    return uh
```

**Expected Results:**
- Solver converges (no singular matrix)
- Error < 0.1 (loose tolerance for sanity check)
- Solution looks physically reasonable (smooth, no oscillations)

---

### Test 3: Material Region Validation

**Purpose:** Verify multi-material meshes have correct region assignments

**Implementation:**
```python
def validate_material_regions(mesh, material_regions):
    """Check material regions are valid"""
    results = {}
    
    for material, elements in material_regions.items():
        print(f"Validating {material}...")
        
        # Non-empty check
        if len(elements) == 0:
            results[material] = False
            continue
        
        # Check unique nodes
        nodes = set()
        for elem in elements:
            nodes.update(elem)
        
        results[material] = True
        print(f"  Elements: {len(elements)}")
        print(f"  Unique nodes: {len(nodes)}")
    
    return all(results.values())
```

---

### Test 4: Geometric Fidelity Check

**Purpose:** Verify simplified mesh approximates original geometry

**Implementation:**
```python
from scipy.spatial import cKDTree
from scipy.spatial.distance import directed_hausdorff

def compute_chamfer_distance(points1, points2):
    """Compute Chamfer distance between two point clouds"""
    tree1 = cKDTree(points1)
    tree2 = cKDTree(points2)
    
    dist1, _ = tree1.query(points2)
    dist2, _ = tree2.query(points1)
    
    return (np.mean(dist1) + np.mean(dist2)) / 2

def validate_geometric_fidelity(original, simplified, threshold=0.1):
    """Check simplified mesh is close to original"""
    chamfer = compute_chamfer_distance(original, simplified)
    
    # Hausdorff distance
    h1 = directed_hausdorff(original, simplified)[0]
    h2 = directed_hausdorff(simplified, original)[0]
    hausdorff = max(h1, h2)
    
    print(f"Chamfer distance: {chamfer:.4f} um")
    print(f"Hausdorff distance: {hausdorff:.4f} um")
    
    return chamfer < threshold and hausdorff < threshold * 2
```

**Expected Results:**
- Chamfer distance < 0.1 um (as reported in thesis)
- Hausdorff distance < 0.2 um

---

## Test Data Generation

### From Thesis Test Cases

Use the three test cases already implemented:
1. **Stack Etching (2D)** - 5-layer stack with trenches
2. **CVD Deposition (2D)** - Conformal coating
3. **CVD Deposition (3D)** - Volume mesh

**Python script to generate test meshes:**
```python
#!/usr/bin/env python3
"""Generate test meshes from ViennaPS simulations"""
import viennaps2d as vps
from vienna_ps_adapter import ViennaPSAdapter
from mesher_2d import load_multiple_poly_files

def generate_stack_etch_mesh():
    """Generate stack etching test case mesh"""
    domain = vps.Domain()
    vps.MakeStack(domain, 0.21, 40.0, 0.0, 15, 
                  2.5, 10.0, 0.0, 15.0, 5.0, False).apply()
    domain.duplicateTopLevelSet(vps.Material.Polymer)
    
    model = vps.FluorocarbonEtching(50., 90., 5.5, 100., 10., 1000., 1.)
    vps.Process(domain, model, 10.).apply()
    
    # Convert to mesh
    adapter = ViennaPSAdapter(domain, z_depth=10.0)
    meshes = adapter.extract_all_levelsets()
    
    # Process with thesis pipeline
    regions, merged, simplified = load_multiple_poly_files(
        meshes, ["Oxide", "Nitride", "Polymer"], epsilon=0.5
    )
    
    return regions, merged, simplified
```

---

## Validation Checklist

### Pre-Simulation Checks

- [ ] Mesh file format is valid (readable by meshplex/Gmsh)
- [ ] All elements are valid (no zero-area/volume elements)
- [ ] Mesh is manifold (for surface meshes)
- [ ] No duplicate vertices (within tolerance)
- [ ] Material regions are non-empty
- [ ] Bounding box is correct

### Quality Checks

- [ ] Minimum angle > 5 degrees (15 preferred)
- [ ] Maximum angle < 120 degrees (for triangles)
- [ ] Aspect ratio < 10:1
- [ ] >90% elements have quality > 0.1
- [ ] No inverted elements
- [ ] Delaunay violations < 1% of edges

### Simulation Checks

- [ ] Poisson equation converges
- [ ] Solution is smooth (no oscillations)
- [ ] Error < 0.1 (loose tolerance)
- [ ] Boundary conditions satisfied

### Geometric Checks

- [ ] Chamfer distance < 0.1 um vs original
- [ ] Hausdorff distance < 0.2 um vs original
- [ ] Material boundaries preserved
- [ ] No gaps or overlaps between materials

---

## Automation

### Test Script Structure

```
tests/
├── __init__.py
├── conftest.py              # pytest fixtures
├── test_mesh_quality.py     # Test 1
├── test_poisson.py          # Test 2
├── test_materials.py        # Test 3
├── test_fidelity.py         # Test 4
├── fixtures/
│   ├── stack_etch.node
│   ├── stack_etch.ele
│   ├── stack_etch.poly
│   └── ...
└── run_all_tests.py         # Main test runner
```

---

## Summary

**Recommended Approach:**
1. Start with **meshplex** for quality metrics (easiest, pure Python)
2. Add **PyVista** for visualization
3. Use **FEniCSx** for Poisson solves if needed (optional)
4. Consider **Gmsh** only if native Triangle/TetGen support is required

**Priority:**
1. **HIGH:** Test 1 (Mesh Quality) - Essential for validation
2. **HIGH:** Test 4 (Geometric Fidelity) - Validates simplification
3. **MEDIUM:** Test 3 (Material Regions) - Important for multi-material
4. **LOW:** Test 2 (Poisson Solve) - Nice to have, not essential

**Time Estimate:**
- Test 1: 2-3 hours
- Test 4: 2-3 hours
- Test 3: 3-4 hours
- Test 2: 4-6 hours (if using FEniCSx)
- **Total: 1-2 days** for basic validation suite

---

## References

- **meshplex:** https://github.com/meshpro/meshplex
- **PyVista:** https://docs.pyvista.org/
- **FEniCSx:** https://fenicsproject.org/
- **Gmsh:** https://gmsh.info/
- **MFEM:** https://mfem.org/
