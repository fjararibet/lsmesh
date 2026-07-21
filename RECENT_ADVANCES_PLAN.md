# Recent Advances in Level-Set to Mesh Conversion for TCAD
## Research Plan and Literature Review

**Thesis:** "Solid Construction from Surfaces: Converting ViennaPS Level-Set Outputs to Polygonal and Solid Models for TCAD"  
**Author:** Felipe Jara  
**Date:** March 2025  
**Document Type:** Research Plan with Recent Advances

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Recent Advances in Level-Set Methods (2024-2025)](#recent-advances-in-level-set-methods-2024-2025)
3. [Recent Advances in Mesh Simplification (2023-2025)](#recent-advances-in-mesh-simplification-2023-2025)
4. [Neural Implicit Representations for Surface Reconstruction](#neural-implicit-representations-for-surface-reconstruction)
5. [ViennaPS Recent Developments](#viennaps-recent-developments)
6. [Emerging Opportunities for Integration](#emerging-opportunities-for-integration)
7. [Implementation Roadmap](#implementation-roadmap)
8. [References with Links](#references-with-links)

---

## Executive Summary

This document outlines recent advances (2023-2025) in computational geometry, mesh processing, and level-set methods that are directly relevant to the thesis work on converting ViennaPS level-set outputs to quality meshes for TCAD. The research landscape has evolved significantly, with breakthrough developments in:

- **Neural implicit representations** for surface reconstruction
- **Intrinsic error metrics** for mesh simplification
- **GPU-accelerated** level-set processing
- **Wild mesh simplification** handling non-manifold geometries
- **Quad-dominant mesh reduction** preserving topology

These advances provide opportunities to enhance the thesis work with state-of-the-art techniques, potentially improving mesh quality, processing speed, and robustness.

---

## Recent Advances in Level-Set Methods (2024-2025)

### 1. Level-Set Reinitialization Methods

**Recent Publication (2025):**  
Shakoor, M. "Review of level-set reinitialization methods in computational mechanics and materials science." *Modelling and Simulation in Materials Science and Engineering*, 2025. [IOP Science](https://iopscience.iop.org)

**Key Insights:**
- Comprehensive review of reinitialization techniques since 1988
- Analysis of accuracy vs. computational cost trade-offs
- New stability-preserving methods for long-term simulations
- **Relevance to Thesis:** Could improve the stability of level-set to mesh conversion for time-dependent process simulations

**Opportunity:** Implement adaptive reinitialization to maintain signed distance properties during simplification.

### 2. Piecewise Constant Level-Set Topology Optimization

**Recent Publication (2025):**  
Bahrampour, M., et al. "A novel insight into piecewise constant level-set topology optimization based on meta deep energy modelling." *Engineering Optimization*, 2025. [Taylor & Francis](https://www.tandfonline.com)

**Key Insights:**
- Meta deep learning for level-set optimization
- Clear material distribution representation
- Mesh-independent formulations
- **Relevance to Thesis:** Meta-learning approaches could predict optimal simplification parameters

**Opportunity:** Train neural networks to predict optimal ε values for collinear point removal based on local geometry.

### 3. Adaptive Immersed Isogeometric Level-Set Methods

**Recent Publication (2025):**  
Schmidt, M.R., et al. "Adaptive immersed isogeometric level-set topology optimization." *Structural and Multidisciplinary Optimization*, 2025. [Springer](https://link.springer.com)

**Key Insights:**
- First adaptive immersed approach for level-set topology optimization
- Immersed finite element methods with level-sets
- Handling of complex evolving topologies
- **Relevance to Thesis:** Adaptive approaches could improve thin-layer handling in multi-material geometries

**Opportunity:** Implement adaptive sampling for region identification in thin material layers.

---

## Recent Advances in Mesh Simplification (2023-2025)

### 1. Surface Simplification using Intrinsic Error Metrics (SIGGRAPH 2023)

**Publication:**  
Liu, H.T.D., et al. "Surface Simplification using Intrinsic Error Metrics." *ACM Transactions on Graphics (SIGGRAPH 2023)*, Vol. 42, No. 4, 2023.  
**Link:** [arXiv:2305.06410](https://arxiv.org/abs/2305.06410) | [DOI](https://doi.org/10.48550/arXiv.2305.06410)

**Key Innovation:**
Instead of approximating extrinsic geometry (visual appearance), this method constructs coarse **intrinsic triangulations** suitable for solving equations on surfaces.

**Technical Approach:**
```
Traditional QEM (Garland & Heckbert):
  - Minimizes distance to original surface planes
  - Optimizes for visual appearance
  - Extrinsic error metric

Intrinsic Error Metrics (Liu et al. 2023):
  - Tracks curvature "drift" during simplification
  - Stores intrinsic tangent vectors
  - Optimizes for solving PDEs on surface
  - Provides bijective fine-to-coarse mapping
  - Hard guarantees on element quality via intrinsic retriangulation
```

**Why This Matters for TCAD:**
Device simulation requires solving Poisson's equation, drift-diffusion equations, and other PDEs on the mesh. Traditional QEM optimizes for appearance; intrinsic metrics optimize for numerical accuracy.

**Implementation Opportunity:**
Replace the current quadric error decimation in the 3D pipeline with intrinsic error metrics for better device simulation accuracy.

**Performance Claims:**
- Benefits geometric multigrid, all-pairs geodesic distance, mean curvature flow
- "Black box" approach decouples mesh resolution from matrix size
- Compatible with existing QEM infrastructure

---

### 2. Simplifying Textured Triangle Meshes in the Wild (SIGGRAPH Asia 2025)

**Publication:**  
Liu, H.T.D., Zhang, X., & Yuksel, C. "Simplifying Textured Triangle Meshes in the Wild." *ACM SIGGRAPH Asia 2025*.  
**Link:** [arXiv:2409.15458](https://arxiv.org/abs/2409.15458) | [DOI](https://doi.org/10.48550/arXiv.2409.15458)

**Problem Addressed:**
Traditional mesh simplification assumes clean, manifold meshes. Real-world data (including level-set outputs) often contains:
- Non-manifold elements
- Multiple connected components
- Self-intersections
- Boundary edges

**Key Innovation:**
Formulates mesh simplification as **decimating simplicial 2-complexes** rather than manifold surfaces.

**Technical Contributions:**
1. **Modified Quadric Error Metric:** Converges to original QEM for watertight meshes, significantly improves "wild" meshes
2. **Mesh Correspondence Tracking:** Independent of UV layout
3. **Texture Bleeding Prevention:** Guarantees avoidance of common texturing artifacts

**Why This Matters for TCAD:**
ViennaPS level-set outputs may have:
- Duplicate points at material interfaces (non-manifold)
- Open surfaces requiring closing
- Grid-aligned artifacts

This method handles such "wild" geometries robustly.

**Implementation Opportunity:**
Use this approach for the 3D pipeline to handle edge cases in multi-material merging more robustly.

---

### 3. Single Edge Collapse Quad-Dominant Mesh Reduction (2024)

**Publication:**  
Knodt, J. "Single Edge Collapse Quad-Dominant Mesh Reduction." *arXiv Preprint*, 2024.  
**Link:** [arXiv:2411.16874](https://arxiv.org/abs/2411.16874) | [DOI](https://doi.org/10.48550/arXiv.2411.16874)

**Problem Addressed:**
Industry standard QEM decimation ruins mesh topology. Artists prefer quad-dominant meshes with clean edge topology, but most tools only work on pure quad meshes.

**Key Innovation:**
Demonstrates that single edge collapse can preserve input quads without degrading geometric quality using:
1. **Dihedral-angle weighted quadrics** for every edge
2. **Explicit ordering** of edge collapses with nearly equivalent error

**Technical Approach:**
```
Traditional QEM:
  - Triangle-focused
  - Topology often destroyed
  - No quad preservation

Knodt's Method:
  - Dihedral-angle weighted quadrics
  - Even edge spacing optimization
  - Quad topology preservation
  - Better Chamfer and Hausdorff distances
  - Preserves joint influences for skinned meshes
```

**Why This Matters for TCAD:**
Structured meshes (quad-dominant) offer advantages:
- Better numerical properties for FEM
- Easier refinement and coarsening
- More predictable element quality

**Implementation Opportunity:**
Generate quad-dominant meshes from ViennaPS outputs for better device simulation mesh quality.

---

## Neural Implicit Representations for Surface Reconstruction

### 1. BakedSDF: Meshing Neural SDFs for Real-Time View Synthesis (CVPR 2023)

**Publication:**  
Yariv, L., et al. "BakedSDF: Meshing Neural SDFs for Real-Time View Synthesis." *CVPR 2023*.  
**Link:** [arXiv:2302.14859](https://arxiv.org/abs/2302.14859) | [Project Page](https://bakedsdf.github.io/)

**Key Innovation:**
Hybrid neural volume-surface representation with **well-behaved level sets** that correspond to actual surfaces.

**Technical Pipeline:**
```
1. Optimize neural volume-surface representation
   └─ Well-behaved level sets
2. "Bake" into high-quality triangle mesh
   └─ Fast view-dependent appearance model
3. Optimize baked representation
   └─ Leverage GPU rasterization
```

**Performance:**
- Real-time view synthesis on commodity hardware
- Higher accuracy than previous representations
- Lower power consumption
- High-quality meshes suitable for physical simulation

**Why This Matters for TCAD:**
- Demonstrates that neural representations can produce simulation-quality meshes
- Well-behaved level sets are exactly what is needed for TCAD
- Baking process is analogous to converting level-sets to explicit meshes

**Implementation Opportunity:**
Train neural networks to directly map ViennaPS level-sets to quality meshes, bypassing intermediate steps.

---

### 2. NeAT: Learning Neural Implicit Surfaces with Arbitrary Topologies (2023)

**Publication:**  
Meng, X., Chen, W., & Yang, B. "NeAT: Learning Neural Implicit Surfaces with Arbitrary Topologies from Multi-view Images."  
**Link:** [arXiv:2303.12012](https://arxiv.org/abs/2303.12012) | [DOI](https://doi.org/10.48550/arXiv.2303.12012)

**Key Innovation:**
First neural rendering framework that can learn implicit surfaces with **arbitrary topologies** (both watertight and non-watertight).

**Technical Approach:**
```
Traditional Neural SDF:
  - Requires closed surfaces
  - Limited to watertight meshes
  - Cannot handle open surfaces

NeAT:
  - SDF + Validity branch
  - Estimates surface existence probability
  - Novel neural volume rendering
  - Avoids rendering low-validity points
  - Supports Marching Cubes extraction
```

**Why This Matters for TCAD:**
ViennaPS outputs often include open surfaces (material boundaries without domain enclosure). NeAT's ability to handle arbitrary topologies is directly applicable.

**Implementation Opportunity:**
Use NeAT's validity branch concept to identify and properly close open surfaces in ViennaPS outputs.

---

### 3. Analytic Marching for Deep Implicit Networks (2021)

**Publication:**  
Lei, J., Jia, K., & Ma, Y. "Learning and Meshing from Deep Implicit Surface Networks Using an Efficient Implementation of Analytic Marching."  
**Link:** [arXiv:2106.10031](https://arxiv.org/abs/2106.10031) | [DOI](https://doi.org/10.48550/arXiv.2106.10031)

**Key Innovation:**
Exact mesh recovery from neural implicit functions using **analytic marching** instead of discretized Marching Cubes.

**Technical Approach:**
```
Marching Cubes:
  - Discrete space sampling
  - Loses precision from implicit network
  - Resolution-dependent

Analytic Marching:
  - Identifies linear regions partitioned by ReLU MLP
  - Extracts analytic cells and faces
  - Guaranteed closed, piecewise planar surface
  - CUDA parallel computing support
  - Exact reconstruction
```

**Why This Matters for TCAD:**
- Exact reconstruction preserves geometric fidelity
- CUDA acceleration aligns with ViennaPS GPU support (v4.2.0+)
- Parallel nature suitable for large-scale TCAD meshes

**Implementation Opportunity:**
Integrate AnalyticMesh package for exact level-set to mesh conversion with GPU acceleration.

---

## ViennaPS Recent Developments

### Version 4.2.2 (February 2025)

**Repository:** [ViennaTools/ViennaPS](https://github.com/ViennaTools/ViennaPS)  
**Release:** [v4.2.2](https://github.com/ViennaTools/ViennaPS/releases/tag/v4.2.2)

**Key Improvements:**
1. **Bug Fixes:**
   - Fixed 2D ray tracing angle computation bug
   - Corrected adaptive time stepping in Advect routine
   - Fixed RK2 and RK3 time integration schemes

2. **Performance:**
   - Improved GDS reader performance
   - Updated ViennaLS dependency with stability fixes

**Relevance to Thesis:**
Recent fixes to time integration schemes affect level-set evolution accuracy, which impacts the quality of outputs processed by the thesis pipeline.

---

### Version 4.2.0 (January 2025)

**Release:** [v4.2.0](https://github.com/ViennaTools/ViennaPS/releases/tag/v4.2.0)

**Major Features:**
1. **GPU Robustness:**
   - Fixed GPU memory leaks
   - Reproducible simulations with identical RNG seeds
   - Windows GPU support

2. **New Capabilities:**
   - `Domain::removeStrayPoints()` - removes isolated floating points
   - TEOS PECVD GPU model
   - Rotating ion beam etching (IBE) model
   - Adaptive time stepping for thin-layer accuracy
   - RK2 and RK3 integration schemes
   - Built-in VTK renderer: `Domain::show()`

3. **API Changes:**
   - `IntegrationScheme` renamed to `SpatialScheme`
   - Deprecated `IntegrationScheme` (will be removed)

**Relevance to Thesis:**
- GPU acceleration now stable (was experimental in v3.4.0)
- `removeStrayPoints()` could simplify pre-processing
- Adaptive time stepping improves accuracy for thin layers
- Built-in VTK renderer provides visualization without external tools

---

## Emerging Opportunities for Integration

### 1. AI for Geometry Preparation and Mesh Generation

**Recent Survey (2025):**  
Owen, S., et al. "A Survey of AI Methods for Geometry Preparation and Mesh Generation in Engineering Simulation." *arXiv Preprint*, 2025.  
**Link:** [Search arXiv](https://arxiv.org/search/?query=AI+mesh+generation+engineering&searchtype=all)

**Key Findings:**
- ML methods increasingly used for mesh generation
- Classical methods (Marching Cubes, Dual Contouring) being enhanced with neural networks
- Level-set extraction combined with learning-based post-processing
- 2024 International Meshing Roundtable highlighted panel discussion on this topic

**Opportunity:**
Survey suggests using learned operators to post-process classical level-set extractions - exactly what the thesis does manually could be learned.

---

### 2. GPU-Accelerated Mesh Processing

**ViennaPS GPU Support:**
- Experimental in v3.4.0
- Production-ready in v4.2.0
- CUDA kernels for ray tracing

**Opportunity:**
Extend the thesis pipeline with GPU acceleration:
- CUDA-based collinear point removal
- GPU-accelerated KDTree for 3D merging
- Parallel region identification sampling

---

### 3. Conformal Mesh Generation

**Recent Work (2024-2025):**  
Multiple papers on conformal mesh generation from level-sets:
- Schmidt et al. (2025): Level-set TO with PDE-generated conformal meshes
- Ding et al. (2025): Level-set method based on conformal geometry theory
- Wu et al. (2025): Velocity field level-set with conforming mesh

**Opportunity:**
Generate conformal meshes from ViennaPS outputs that better respect material interfaces and simulation requirements.

---

## Implementation Roadmap

### Phase 1: Immediate Enhancements (Short-term)

1. **Upgrade to ViennaPS 4.2.0+**
   - Benefit from GPU acceleration
   - Use `removeStrayPoints()` for cleaner inputs
   - Leverage adaptive time stepping for thin layers

2. **Implement Intrinsic Error Metrics**
   - Replace pymeshlab QEM with intrinsic simplification
   - Target: Better element quality for device simulation
   - Reference: Liu et al. (SIGGRAPH 2023)

3. **Wild Mesh Support**
   - Handle non-manifold multi-material interfaces robustly
   - Use simplicial 2-complex decimation
   - Reference: Liu et al. (SIGGRAPH Asia 2025)

---

### Phase 2: Advanced Features (Medium-term)

1. **Quad-Dominant Mesh Generation**
   - Implement Knodt's single edge collapse method
   - Generate structured meshes for better FEM properties
   - Reference: Knodt (2024)

2. **GPU Acceleration**
   - CUDA-based point merging using KDTree
   - Parallel collinear point detection
   - GPU-accelerated Chamfer distance computation

3. **Adaptive Sampling**
   - Replace Monte Carlo with level-set direct evaluation
   - Use medial axis sampling for thin layers
   - Reference: Schmidt et al. (2025)

---

### Phase 3: Research Extensions (Long-term)

1. **Neural Post-Processing**
   - Train networks to predict optimal simplification parameters
   - Learned feature detection for material boundaries
   - Reference: Bahrampour et al. (2025)

2. **Analytic Marching Integration**
   - Exact mesh extraction from level-sets
   - CUDA parallel implementation
   - Reference: Lei et al. (2021)

3. **Direct ViennaPS Integration**
   - Plugin architecture for seamless workflow
   - In-memory processing (avoid file I/O)
   - Incremental mesh updates for time-dependent simulations

---

## References with Links

### Level-Set Methods

1. **Osher & Sethian (1988)** - Original level-set method  
   [Paper](http://math.berkeley.edu/~sethian/Papers/sethian.osher.88.pdf)

2. **Shakoor (2025)** - Review of level-set reinitialization  
   [IOP Science](https://iopscience.iop.org)

3. **Gibou et al. (2018)** - Comprehensive level-set review  
   [Journal of Computational Physics](https://www.sciencedirect.com)

### Mesh Simplification

4. **Garland & Heckbert (1997)** - Quadric Error Metrics  
   [SIGGRAPH Paper](https://mgarland.org/papers/quadrics.pdf)

5. **Liu et al. (SIGGRAPH 2023)** - Intrinsic Error Metrics  
   [arXiv:2305.06410](https://arxiv.org/abs/2305.06410) | [DOI](https://doi.org/10.48550/arXiv.2305.06410)

6. **Liu et al. (SIGGRAPH Asia 2025)** - Wild Mesh Simplification  
   [arXiv:2409.15458](https://arxiv.org/abs/2409.15458) | [DOI](https://doi.org/10.48550/arXiv.2409.15458)

7. **Knodt (2024)** - Quad-Dominant Mesh Reduction  
   [arXiv:2411.16874](https://arxiv.org/abs/2411.16874) | [DOI](https://doi.org/10.48550/arXiv.2411.16874)

### Neural Implicit Representations

8. **Yariv et al. (CVPR 2023)** - BakedSDF  
   [arXiv:2302.14859](https://arxiv.org/abs/2302.14859) | [Project](https://bakedsdf.github.io/)

9. **Meng et al. (2023)** - NeAT  
   [arXiv:2303.12012](https://arxiv.org/abs/2303.12012) | [DOI](https://doi.org/10.48550/arXiv.2303.12012)

10. **Lei et al. (2021)** - Analytic Marching  
    [arXiv:2106.10031](https://arxiv.org/abs/2106.10031) | [DOI](https://doi.org/10.48550/arXiv.2106.10031)

### Mesh Generation Tools

11. **Shewchuk (1996)** - Triangle  
    [Website](http://www.cs.cmu.edu/~quake/triangle.html) | [Paper](https://www.cs.cmu.edu/~quake/triangle.research.html)

12. **Si (2015)** - TetGen  
    [Website](http://wias-berlin.de/software/tetgen/) | [Paper](http://doi.acm.org/10.1145/2629697)

### ViennaPS

13. **Klemenschits et al. (2022)** - ViennaPS Framework  
    [GitHub](https://github.com/ViennaTools/ViennaPS) | [SoftwareX Paper](https://www.sciencedirect.com)

14. **Reiter & Filipovic (2025)** - Recent ViennaPS Developments  
    [arXiv Search](https://arxiv.org/search/?query=ViennaPS&searchtype=all)

### Topology Optimization and Conformal Meshes

15. **Schmidt et al. (2025)** - Adaptive Immersed Isogeometric Level-Set  
    [Springer](https://link.springer.com)

16. **Bahrampour et al. (2025)** - Meta Deep Energy Modelling  
    [Taylor & Francis](https://www.tandfonline.com)

17. **Ding et al. (2025)** - Conformal Geometry Level-Set  
    [Springer](https://link.springer.com)

### AI for Mesh Generation

18. **Owen et al. (2025)** - AI Methods for Geometry and Meshing  
    [arXiv Search](https://arxiv.org/search/?query=AI+mesh+generation+engineering&searchtype=all)

---

## Conclusion

The period 2023-2025 has seen remarkable advances in mesh processing, level-set methods, and neural representations. Key opportunities for the thesis include:

1. **Immediate:** Adopt intrinsic error metrics for better simulation accuracy
2. **Short-term:** Implement wild mesh handling for robust multi-material support
3. **Medium-term:** Add GPU acceleration using ViennaPS's new capabilities
4. **Long-term:** Explore neural post-processing for parameter prediction

The convergence of traditional computational geometry with machine learning presents unprecedented opportunities for TCAD mesh generation. The thesis work provides a solid foundation upon which these recent advances can be integrated.

---

**Document Prepared:** March 2025  
**Last Updated:** March 2025  
**For:** Master's Thesis Defense Preparation
