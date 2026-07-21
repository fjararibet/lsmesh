"""Execution boundary for ViennaPS viewer presets."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, fields
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeVar, cast

from lsmesher.api import BuildOptions, ViennaPSDomain
from lsmesher.meshing import MesherOptions, MeshingOptions, mesh
from lsmesher.pipeline_3d import DecimationOptions3D

if TYPE_CHECKING:
    from lsmesher.results import MeshResult2D, MeshResult3D

PRESET_REQUEST_ENV = "LSMESHER_PRESET_REQUEST"
OptionsT = TypeVar("OptionsT")


def _dataclass_options(
    option_type: type[OptionsT], values: dict[str, Any]
) -> OptionsT:
    names = {item.name for item in fields(option_type)}
    return option_type(**{key: value for key, value in values.items() if key in names})


def _options(request: dict[str, Any]) -> MeshingOptions:
    build_values = dict(request.get("build", {}))
    decimation = _dataclass_options(
        DecimationOptions3D, dict(build_values.pop("decimation", {}))
    )
    build = _dataclass_options(
        BuildOptions,
        {**build_values, "decimation": decimation},
    )
    mesher = _dataclass_options(MesherOptions, dict(request.get("mesher", {})))
    return MeshingOptions(
        build=build,
        mesher=mesher,
        run_mesher=bool(request.get("run_mesher", True)),
        validate=bool(request.get("validate", True)),
    )


def _request(dimension: int | None) -> dict[str, Any]:
    request_path = os.environ.get(PRESET_REQUEST_ENV)
    if request_path:
        return cast(
            "dict[str, Any]",
            json.loads(Path(request_path).read_text(encoding="utf-8")),
        )
    if dimension not in (2, 3):
        msg = "run_preset() needs dimension=2 or dimension=3 outside the viewer"
        raise ValueError(msg)
    return {
        "dimension": dimension,
        "output_path": str(Path.cwd() / "mesh.vtu"),
        "manifest_path": str(Path.cwd() / "lsmesher-preset-result.json"),
    }


def _artifacts(result: MeshResult2D | MeshResult3D) -> list[str]:
    paths = {*result.output_paths}
    if result.log_path is not None:
        paths.add(result.log_path)
    for directory in {path.parent for path in paths}:
        paths.update(path for path in directory.iterdir() if path.is_file())
    return [str(path.resolve()) for path in sorted(paths)]


def run_preset(
    domain: ViennaPSDomain,
    *,
    dimension: Literal[2, 3] | None = None,
) -> MeshResult2D | MeshResult3D:
    """Mesh a completed ViennaPS domain using viewer-supplied SDK options."""
    request = _request(dimension)
    resolved_dimension = cast("Literal[2, 3]", int(request["dimension"]))
    output_path = Path(request["output_path"]).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = mesh(
        domain,
        output_path,
        dimension=resolved_dimension,
        options=_options(request),
    )
    manifest = {
        "dimension": resolved_dimension,
        "output": str(output_path),
        "materials": [asdict(material) for material in result.materials],
        "artifacts": _artifacts(result),
    }
    manifest_path = Path(request["manifest_path"]).resolve()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return result
