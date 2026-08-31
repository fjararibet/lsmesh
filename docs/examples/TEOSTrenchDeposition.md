# TEOS trench deposition

TEOS oxide deposition into trenches with one or several precursors.

## Single precursor

Run from the repository root:

```bash
cd docs/examples/TEOSTrenchDeposition && uv run python singleTEOS.py -D 2 singleTEOS_config.txt
```

```python
--8<-- "examples/TEOSTrenchDeposition/singleTEOS.py"
```

### Configuration

```text
--8<-- "examples/TEOSTrenchDeposition/singleTEOS_config.txt"
```

## Multiple precursors

Run from the repository root:

```bash
cd docs/examples/TEOSTrenchDeposition && uv run python multiTEOS.py -D 2 multiTEOS_config.txt
```

```python
--8<-- "examples/TEOSTrenchDeposition/multiTEOS.py"
```

### Configuration

```text
--8<-- "examples/TEOSTrenchDeposition/multiTEOS_config.txt"
```
