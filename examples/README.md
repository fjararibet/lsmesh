# ViennaPS scripts using lsmesh

This directory mirrors the Python examples from the
[official ViennaPS repository](https://github.com/ViennaTools/ViennaPS/tree/master/examples).
The ViennaPS geometry and process code is kept in each script so it can be read,
copied, and modified exactly like the upstream example. The output step is the
intentional difference:

```python
import lsmesh

# ...ordinary ViennaPS geometry and process code...

lsmesh.mesh(geometry, "mesh.vtu", dimension=args.dim)
```

Every example is a normal standalone script. Examples with a configuration
file are run from their own directory, as in upstream:

```bash
cd examples/trenchDeposition
uv run python trenchDeposition.py -D 3 config.txt

cd ../boschProcess
uv run python boschProcessRayTracing.py -D 3 configBoschRayTracing.txt

cd ../selectiveEpitaxy
uv run python selectiveEpitaxy.py -D 3 config.txt
```

Included process examples:

- DRAM wiggling and GDS import
- SiGe selective etching
- single- and multi-precursor TEOS deposition
- atomic layer deposition
- blazed-grating, Bosch, Faraday-cage, hole, ion-beam, and stack etching
- cantilever wet etching
- FinFET, SAQP, and stacked-nanowire emulation
- selective epitaxy and geometric/particle trench deposition
- fin, LOCOS, step, and trench oxidation
- CSV-driven 2D and 3D sputter deposition
- temporal-scheme simple etching

The scripts and configuration data derived from ViennaPS retain its
GPL-3.0-or-later licensing.

