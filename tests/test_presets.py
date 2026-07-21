"""Tests for the SDK preset execution boundary."""

import json
from pathlib import Path
from types import SimpleNamespace

from lsmesher.presets import PRESET_REQUEST_ENV, run_preset
from lsmesher.results import MaterialInfo


def test_run_preset_uses_request_options_and_writes_manifest(
    tmp_path: Path, monkeypatch
):
    request_path = tmp_path / "request.json"
    output_path = tmp_path / "mesh.vtu"
    manifest_path = tmp_path / "result.json"
    request_path.write_text(
        json.dumps(
            {
                "dimension": 3,
                "output_path": str(output_path),
                "manifest_path": str(manifest_path),
                "run_mesher": False,
                "build": {
                    "epsilon": 1e-5,
                    "decimation": {"enabled": False},
                },
                "mesher": {"tetgen_quality_ratio": 1.4},
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    def fake_mesh(domain, output, *, dimension, options):
        captured.update(
            domain=domain,
            output=output,
            dimension=dimension,
            options=options,
        )
        output_path.write_text("mesh", encoding="utf-8")
        return SimpleNamespace(
            output_paths=(output_path,),
            log_path=None,
            materials=(MaterialInfo(region=1, material_id=10, name="Si"),),
        )

    monkeypatch.setenv(PRESET_REQUEST_ENV, str(request_path))
    monkeypatch.setattr("lsmesher.presets.mesh", fake_mesh)
    domain = object()

    run_preset(domain)  # type: ignore[arg-type]

    assert captured["domain"] is domain
    assert captured["dimension"] == 3
    assert captured["options"].run_mesher is False
    assert captured["options"].build.epsilon == 1e-5
    assert captured["options"].build.decimation.enabled is False
    assert captured["options"].mesher.tetgen_quality_ratio == 1.4
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["output"] == str(output_path)
    assert manifest["materials"] == [
        {"region": 1, "material_id": 10, "name": "Si"}
    ]
