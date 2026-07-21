"""Resolve paths to bundled binaries."""

from __future__ import annotations

from pathlib import Path

_BIN_DIR = Path(__file__).resolve().parent / "bin"

TRIANGLE: Path = _BIN_DIR / "triangle"
"""Absolute path to the bundled Triangle binary."""

SHOWME: Path = _BIN_DIR / "showme"
"""Absolute path to the bundled Show Me binary."""
