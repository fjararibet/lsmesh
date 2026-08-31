"""Static smoke tests for the copied ViennaPS example scripts."""

from pathlib import Path

import pytest

ENTRY_POINTS = tuple(
    path
    for path in sorted(Path("docs/examples").glob("*/*.py"))
    if path.name
    not in {
        "generateRatesData.py",
        "SiGeStackGeometry.py",
        "visualizeDomain.py",
    }
)


@pytest.mark.parametrize("example", ENTRY_POINTS)
def test_example_compiles_and_uses_lsmesh(example: Path):
    source = example.read_text(encoding="utf-8")

    compile(source, str(example), "exec")
    assert "lsmesh.mesh(" in source


def test_examples_cover_the_official_process_catalog():
    directories = {path.parent.name for path in ENTRY_POINTS}

    assert {
        "DRAMWiggling",
        "GDSReader",
        "TEOSTrenchDeposition",
        "atomicLayerDeposition",
        "boschProcess",
        "emulation",
        "finOxidation",
        "locosOxidation",
        "sputterDeposition",
        "stepOxidation",
        "trenchOxidation",
    } <= directories
