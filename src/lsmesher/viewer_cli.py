"""Optional Streamlit viewer entry point."""

from __future__ import annotations

from importlib.util import find_spec


def main() -> None:
    missing = [
        package
        for package in ("plotly", "pyvista", "streamlit")
        if find_spec(package) is None
    ]
    if missing:
        packages = ", ".join(missing)
        message = (
            f"The lsmesher viewer requires the 'viewer' extra ({packages} missing).\n"
            'Install it with: uv add "lsmesher[viewer]"'
        )
        raise SystemExit(message)

    from lsmesher.viewer import main as viewer_main  # noqa: PLC0415

    viewer_main()
