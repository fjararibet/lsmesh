# SiGe selective etching

Selective isotropic etching of a SiGe stack with CF4/O2 chemistry.

## Etching

Run from the repository root:

```bash
cd docs/examples/SiGeSelectiveEtching && uv run python SiGeEtching.py -D 2 config_CF4O2.txt
```

```python
--8<-- "examples/SiGeSelectiveEtching/SiGeEtching.py"
```

### Configuration

```text
--8<-- "examples/SiGeSelectiveEtching/config_CF4O2.txt"
```

## Stack geometry helper

Run from the repository root:

```bash
cd docs/examples/SiGeSelectiveEtching && uv run python SiGeStackGeometry.py
```

```python
--8<-- "examples/SiGeSelectiveEtching/SiGeStackGeometry.py"
```
