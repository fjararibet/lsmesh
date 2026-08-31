# Examples

These examples mirror the Python examples from the
[official ViennaPS repository](https://github.com/ViennaTools/ViennaPS/tree/master/examples).
The ViennaPS geometry and process code is kept in each script so
it can be read, copied, and modified exactly like the upstream
example. The output step is the intentional difference:

```python
import lsmesh

# ...ordinary ViennaPS geometry and process code...

lsmesh.mesh(geometry, "mesh.vtu", dimension=args.dim)
```

Every example is a normal standalone script in `docs/examples/`.
Examples with a configuration file are run from their own
directory:

```bash
cd docs/examples/trenchDeposition
uv run python trenchDeposition.py -D 3
```

## Deposition

- [Atomic layer deposition](atomicLayerDeposition.md)
- [Selective epitaxy](selectiveEpitaxy.md)
- [Sputter deposition](sputterDeposition.md)
- [TEOS trench deposition](TEOSTrenchDeposition.md)
- [Trench deposition](trenchDeposition.md)
- [Geometric trench deposition](trenchDepositionGeometric.md)

## Etching

- [Blazed grating etching](blazedGratingsEtching.md)
- [Bosch process](boschProcess.md)
- [Cantilever wet etching](cantileverWetEtching.md)
- [DRAM wiggling](DRAMWiggling.md)
- [Faraday-cage etching](faradayCageEtching.md)
- [Hole etching](holeEtching.md)
- [Ion-beam etching](ionBeamEtching.md)
- [SiGe selective etching](SiGeSelectiveEtching.md)
- [Simple etching](simpleEtching.md)
- [Stack etching](stackEtching.md)

## Oxidation

- [Fin oxidation](finOxidation.md)
- [LOCOS oxidation](locosOxidation.md)
- [Oxide regrowth](oxideRegrowth.md)
- [Step oxidation](stepOxidation.md)
- [Trench oxidation](trenchOxidation.md)

## Import and emulation

- [GDS import](GDSReader.md)
- [Process emulation](emulation.md)

The scripts and configuration data derived from ViennaPS retain
its GPL-3.0-or-later licensing.
