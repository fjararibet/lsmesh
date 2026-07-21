# SDK Viewer Presets

Streamlit presets execute ordinary ViennaPS programs in an isolated subprocess
and pass the completed live domain directly to the lsmesher Python SDK. Interface
VTP files are no longer an intermediate meshing format, so ViennaPS material IDs
survive into Triangle/TetGen and the resulting VTU.

## Adding a preset

A preset directory contains a ViennaPS script, its normal configuration file,
and `preset.toml`:

```text
viewer_presets/myProcess/
├── config.txt
├── myProcess.py
└── preset.toml
```

The metadata is deliberately small:

```toml
name = "My Process"
description = "Run and mesh my ViennaPS process."
script = "myProcess.py"
config = "config.txt"
dimension = 3
runner = "sdk"
assets = ["layout.gds", "rates.csv"]
```

Write the simulation as usual. The only integration code is the import and the
final call with the live domain:

```python
from argparse import ArgumentParser

import viennaps as vps

from lsmesher import run_preset

parser = ArgumentParser()
parser.add_argument("-D", dest="dim", type=int, default=3)
parser.add_argument("filename")
args = parser.parse_args()

vps.setDimension(args.dim)
params = vps.readConfigFile(args.filename)
domain = vps.Domain(
    gridDelta=params["gridDelta"],
    xExtent=params["xExtent"],
    yExtent=params["yExtent"],
)

# Normal ViennaPS geometry and process code goes here.

run_preset(domain, dimension=args.dim)
```

There is no interface export, material sidecar, lsmesher CLI invocation, or
manual option parsing. The viewer supplies its build, decimation, and external
mesher controls to `run_preset()` through a private request file.

Files listed in `assets` are copied beside the editable configuration in the
isolated working directory, so existing ViennaPS code may continue opening them
by their normal relative names.

## Execution model

The subprocess boundary is intentional. ViennaPS has process-wide dimension
state, and PyMeshLab/native mesher failures must not terminate Streamlit. The
preset process performs this complete sequence:

```text
ViennaPS simulation -> live Domain -> lsmesher.mesh() -> VTU/VTP + manifest
```

The manifest declares the output, material metadata, and generated artifacts.
The viewer renders that declared output directly; it does not feed it back
through the file-based CLI.

Simulation and meshing run only after **Generate preset** or
**Recompute outputs** is pressed. Rendering-only changes reuse the last result.

## Standalone use

`run_preset()` also works outside Streamlit. Without a viewer request it uses
the supplied dimension and writes `mesh.vtu` plus
`lsmesher-preset-result.json` in the current directory.

The request protocol is an implementation detail for the viewer. Application
code should call the normal `mesh()` SDK directly when it needs explicit output
paths or `MeshingOptions`.

## ViennaPS example coverage

The viewer currently exposes 26 SDK presets covering every Python example in
the adjacent ViennaPS checkout that produces a completed `viennaps.Domain`.
Separate presets are provided for the two TEOS, two sputter deposition, and
three Bosch variants, as well as the full FinFET, SAQP, and stacked-nanowire
emulation flows.

Python files that are plotting/data-generation utilities are intentionally not
presets: `plotCSV.py`, `interpolationDemo/plot.py`, `generateRatesData.py`, and
`visualizeDomain.py`. `GDSReader2D.py` only exports blurred ViennaLS layers and
does not construct a ViennaPS material domain. `SiGeStackGeometry.py` is used by
the SiGe Selective Etching preset rather than duplicated as a second process.
