# Bosch process

Deep reactive-ion etching alternating an etch step with fluoropolymer passivation. Three variants are included.

## Ray tracing

Run from the repository root:

```bash
cd docs/examples/boschProcess && uv run python boschProcessRayTracing.py -D 3 configBoschRayTracing.txt
```

```python
--8<-- "examples/boschProcess/boschProcessRayTracing.py"
```

### Configuration

```text
--8<-- "examples/boschProcess/configBoschRayTracing.txt"
```

## Process simulation

Run from the repository root:

```bash
cd docs/examples/boschProcess && uv run python boschProcessSimulate.py -D 2 config.txt
```

```python
--8<-- "examples/boschProcess/boschProcessSimulate.py"
```

### Configuration

```text
--8<-- "examples/boschProcess/config.txt"
```

## Geometric emulation

Run from the repository root:

```bash
cd docs/examples/boschProcess && uv run python boschProcessEmulate.py -D 2
```

```python
--8<-- "examples/boschProcess/boschProcessEmulate.py"
```
