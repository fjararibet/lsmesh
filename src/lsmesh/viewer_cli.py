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
            f"The lsmesh viewer requires the 'viewer' extra ({packages} missing).\n"
            'Install it with: uv add "lsmesh[viewer]"'
        )
        raise SystemExit(message)

    from lsmesh.viewer import main as viewer_main  # noqa: PLC0415

    viewer_main()
