"""Tests for Streamlit viewer preset discovery."""

import io
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest
import pyvista as pv

from lsmesher.cli import MesherOptions
from lsmesher.pipeline_3d import DecimationOptions3D
from lsmesher.viewer import (
    PRESETS_DIR_ENV,
    Preset,
    ProcessedMeshOptions,
    PyVistaPngOptions,
    _decimation_cli_flags,
    _geometry_bounding_box_volume,
    _load_preset,
    _mesh_edge_coordinates,
    _preset_data_zip,
    _preset_dimension,
    _preset_original_mesh_files,
    _preset_output_dir,
    _presets,
    _processed_mesh_retry_options,
    _processed_tetgen_log_path,
    _pyvista_screenshot,
    _read_config_entries,
    _run_2d_polygon_preview,
    _run_pipeline,
    _set_png_camera,
    _tetgen_volume_slider_options,
    _write_2d_polygon_preview_output,
    _write_config_with_values,
    _write_processed_mesh_output,
)


def test_presets_require_metadata(tmp_path, monkeypatch):
    """Preset directories without preset.toml are hidden for now."""
    presets_dir = tmp_path / "viewer_presets"
    preset_dir = presets_dir / "large_case"
    preset_dir.mkdir(parents=True)
    (preset_dir / "interface_10.vtp").write_text("", encoding="utf-8")
    (preset_dir / "interface_02.vtp").write_text("", encoding="utf-8")
    (preset_dir / "notes.txt").write_text("ignored", encoding="utf-8")
    monkeypatch.setenv(PRESETS_DIR_ENV, str(presets_dir))

    assert _presets(tmp_path) == []


def test_all_project_presets_use_sdk_generators(monkeypatch):
    """Every project preset meshes its live ViennaPS domain through the SDK."""
    monkeypatch.delenv(PRESETS_DIR_ENV, raising=False)

    presets = _presets(Path.cwd())

    assert {preset.name for preset in presets} == {
        "Blazed Gratings Etching",
        "Bosch Process",
        "Faraday Cage Etching",
        "Hole Etching",
        "Ion Beam Etching",
        "Multi TEOS",
        "Selective Epitaxy",
        "Single TEOS",
        "Stack Etching",
        "Trench Deposition",
        "Trench Deposition Geometric",
    }
    assert all(preset.runner == "sdk" for preset in presets)
    assert all(not preset.files for preset in presets)
    assert all(preset.script and preset.config for preset in presets)


def test_preset_dimension_detects_2d_fixture():
    """2D line VTP files are classified as 2D presets."""
    assert (
        _preset_dimension((Path("tests/end_to_end/fixtures/2d/interface_0.vtp"),)) == 2
    )


def test_preset_dimension_detects_3d_fixture():
    """3D polygon VTP files are classified as 3D presets."""
    assert (
        _preset_dimension((Path("tests/end_to_end/fixtures/3d/interface_1.vtp"),)) == 3
    )


def test_tetgen_volume_slider_scales_with_geometry_bounds():
    """Volume stops span useful tetrahedron counts in current model units."""
    input_paths = [Path("tests/end_to_end/fixtures/3d/interface_1.vtp")]

    bounding_volume = _geometry_bounding_box_volume(input_paths)
    options = _tetgen_volume_slider_options(input_paths)

    assert bounding_volume > 0
    assert options[0] == 0.0
    assert options[1] == pytest.approx(bounding_volume * 1e-6)
    assert options[-1] == pytest.approx(bounding_volume * 1e-1)
    assert list(options) == sorted(options)


def test_preset_dimension_prefers_2d_for_mixed_files():
    """Mixed folders are treated as 2D when line interfaces are present."""
    assert (
        _preset_dimension(
            (
                Path("tests/end_to_end/fixtures/3d/interface_1.vtp"),
                Path("tests/end_to_end/fixtures/2d/interface_0.vtp"),
            )
        )
        == 2
    )


def test_presets_skip_directories_without_vtp(tmp_path, monkeypatch):
    """Directories without VTP files are not shown as presets."""
    presets_dir = tmp_path / "viewer_presets"
    empty_preset = presets_dir / "empty_case"
    empty_preset.mkdir(parents=True)
    (empty_preset / "mesh.vtu").write_text("", encoding="utf-8")
    monkeypatch.setenv(PRESETS_DIR_ENV, str(presets_dir))

    assert _presets(tmp_path) == []


def test_presets_read_metadata_backed_runnable_preset(tmp_path, monkeypatch):
    """preset.toml declares script-backed presets without committed VTP files."""
    presets_dir = tmp_path / "viewer_presets"
    preset_dir = presets_dir / "case"
    preset_dir.mkdir(parents=True)
    (preset_dir / "preset.toml").write_text(
        """name = "Case"
description = "Generate case."
script = "case.py"
config = "config.txt"
dimension = 3
original_outputs = ["original_mesh.vtp", "original_mesh_volume.vtu"]
""",
        encoding="utf-8",
    )
    (preset_dir / "case.py").write_text("", encoding="utf-8")
    (preset_dir / "config.txt").write_text("gridDelta=1\n", encoding="utf-8")
    monkeypatch.setenv(PRESETS_DIR_ENV, str(presets_dir))

    presets = _presets(tmp_path)

    assert len(presets) == 1
    assert presets[0].name == "Case"
    assert presets[0].dimension == 3
    assert presets[0].script == preset_dir / "case.py"
    assert presets[0].config == preset_dir / "config.txt"
    assert presets[0].original_patterns == (
        "original_mesh.vtp",
        "original_mesh_volume.vtu",
    )


def test_processed_mesh_retry_options_keep_selected_settings():
    """3D processed mesh retries rerun without changing decimation settings."""
    attempts = _processed_mesh_retry_options(
        [Path("tests/end_to_end/fixtures/3d/interface_1.vtp")],
        ProcessedMeshOptions(
            epsilon=1e-6,
            output_format="vtp",
            run_mesher=True,
            decimation=DecimationOptions3D(
                enabled=True,
                target_faces=700,
                quality_threshold=0.3,
                optimal_placement=True,
            ),
        ),
    )

    assert [label for label, _options, _reason in attempts] == [
        "selected settings",
        "same settings retry 1",
        "same settings retry 2",
    ]
    for _label, options, reason in attempts[1:]:
        assert options.decimation.enabled is True
        assert options.decimation.target_faces == 700
        assert options.decimation.quality_threshold == 0.3
        assert options.decimation.optimal_placement is True
        assert reason


def test_decimation_cli_flags_select_scalable_target_mode():
    total_flags = _decimation_cli_flags(DecimationOptions3D(target_total_faces=12_000))
    edge_flags = _decimation_cli_flags(DecimationOptions3D(target_edge_length=0.2))

    assert (
        total_flags[total_flags.index("--decimate-target-total-faces") + 1] == "12000"
    )
    assert edge_flags[edge_flags.index("--decimate-target-edge-length") + 1] == "0.2"


def test_metadata_backed_preset_uses_existing_generated_files(tmp_path, monkeypatch):
    """preset.toml can explicitly declare generated output files."""
    presets_dir = tmp_path / "viewer_presets"
    preset_dir = presets_dir / "case"
    preset_dir.mkdir(parents=True)
    output_path = (
        tmp_path / "viewer_outputs" / "Case" / "generated_preset" / "interface_0.off"
    )
    output_path.parent.mkdir(parents=True)
    output_path.write_text("existing", encoding="utf-8")
    (preset_dir / "preset.toml").write_text(
        """name = "Case"
script = "case.py"
config = "config.txt"
dimension = 3
outputs = "../../viewer_outputs/Case/generated_preset/*.off"
""",
        encoding="utf-8",
    )
    (preset_dir / "case.py").write_text("", encoding="utf-8")
    (preset_dir / "config.txt").write_text("gridDelta=1\n", encoding="utf-8")
    monkeypatch.setenv(PRESETS_DIR_ENV, str(presets_dir))

    preset = _presets(tmp_path)[0]
    files, message = _load_preset(preset, tmp_path)

    assert files == [output_path]
    assert message == "Loaded committed fixture files."


def test_metadata_backed_preset_uses_explicit_committed_outputs(tmp_path, monkeypatch):
    """Committed outputs must be declared in preset.toml."""
    presets_dir = tmp_path / "viewer_presets"
    preset_dir = presets_dir / "case"
    preset_dir.mkdir(parents=True)
    output_path = preset_dir / "interface_0.vtp"
    shutil.copyfile("tests/end_to_end/fixtures/3d/interface_1.vtp", output_path)
    (preset_dir / "preset.toml").write_text(
        """name = "Case"
script = "case.py"
config = "config.txt"
dimension = 3
outputs = "interface_*.vtp"
""",
        encoding="utf-8",
    )
    (preset_dir / "case.py").write_text("", encoding="utf-8")
    (preset_dir / "config.txt").write_text("gridDelta=1\n", encoding="utf-8")
    monkeypatch.setenv(PRESETS_DIR_ENV, str(presets_dir))

    preset = _presets(tmp_path)[0]

    assert preset.files == (output_path,)


def test_metadata_backed_preset_does_not_guess_outputs(tmp_path, monkeypatch):
    """Runnable presets do not load arbitrary VTP files beside scripts."""
    presets_dir = tmp_path / "viewer_presets"
    preset_dir = presets_dir / "case"
    preset_dir.mkdir(parents=True)
    shutil.copyfile(
        "tests/end_to_end/fixtures/3d/interface_1.vtp", preset_dir / "final_hull.vtp"
    )
    (preset_dir / "preset.toml").write_text(
        """name = "Case"
script = "case.py"
config = "config.txt"
dimension = 3
""",
        encoding="utf-8",
    )
    (preset_dir / "case.py").write_text("", encoding="utf-8")
    (preset_dir / "config.txt").write_text("gridDelta=1\n", encoding="utf-8")
    monkeypatch.setenv(PRESETS_DIR_ENV, str(presets_dir))

    preset = _presets(tmp_path)[0]

    assert preset.files == ()


def test_generated_output_directories_need_toml_presets(tmp_path, monkeypatch):
    """Generated run outputs are selectable only through preset.toml."""
    presets_dir = tmp_path / "viewer_presets"
    preset_dir = presets_dir / "generated_case"
    preset_dir.mkdir(parents=True)
    run_dir = tmp_path / "viewer_outputs" / "viennaps_examples" / "runs" / "case3d"
    run_dir.mkdir(parents=True)
    output_path = run_dir / "interface_0.vtp"
    shutil.copyfile("tests/end_to_end/fixtures/3d/interface_1.vtp", output_path)
    (preset_dir / "preset.toml").write_text(
        """name = "Case 3D"
dimension = 3
outputs = "../../viewer_outputs/viennaps_examples/runs/case3d/interface_*.vtp"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv(PRESETS_DIR_ENV, str(presets_dir))

    presets = _presets(tmp_path)

    assert len(presets) == 1
    assert presets[0].name == "Case 3D"
    assert presets[0].dimension == 3
    assert presets[0].files == (output_path,)


def test_config_entries_parse_key_value_lines(tmp_path):
    """Preset config editing exposes simple key=value entries."""
    config_path = tmp_path / "config.txt"
    config_path.write_text(
        "# comment\ngridDelta = 0.4 # um\nname=value\n",
        encoding="utf-8",
    )

    entries = _read_config_entries(config_path)

    assert [(entry.key, entry.value) for entry in entries] == [
        ("gridDelta", "0.4"),
        ("name", "value"),
    ]


def test_write_config_with_values_preserves_comments(tmp_path):
    """Edited preset configs keep non-value lines and inline comments."""
    source_path = tmp_path / "config.txt"
    output_path = tmp_path / "edited.txt"
    source_path.write_text(
        "# comment\ngridDelta = 0.4 # um\nname=value\n",
        encoding="utf-8",
    )

    _write_config_with_values(source_path, output_path, {"gridDelta": "0.2"})

    assert output_path.read_text(encoding="utf-8") == (
        "# comment\ngridDelta = 0.2  # um\nname=value\n"
    )


def test_load_preset_runs_script_with_dimension_and_edited_config(tmp_path):
    """Runnable presets execute with -D, dimension, and a generated config file."""
    script_path = tmp_path / "make.py"
    script_path.write_text(
        """import argparse
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument("-D", dest="dim", type=int)
parser.add_argument("filename")
args = parser.parse_args()
config = Path(args.filename).read_text(encoding="utf-8")
Path("interface_0.off").write_text(f"dim={args.dim};{config}", encoding="utf-8")
Path("original_mesh.vtu").write_text("native", encoding="utf-8")
""",
        encoding="utf-8",
    )
    config_path = tmp_path / "config.txt"
    config_path.write_text("gridDelta=0.4\n", encoding="utf-8")
    preset = Preset(
        name="Case",
        description="Generate case.",
        dimension=3,
        script=script_path,
        config=config_path,
        directory=tmp_path,
        original_patterns=("original_mesh.vtu",),
    )

    files, message = _load_preset(
        preset,
        Path.cwd(),
        config_values={"gridDelta": "0.2"},
    )

    assert len(files) == 1
    assert files[0].name == "interface_0.off"
    assert "Generated 1 file" in message
    assert files[0].read_text(encoding="utf-8") == "dim=3;gridDelta = 0.2\n"
    assert _preset_original_mesh_files(preset, Path.cwd(), files) == [
        files[0].with_name("original_mesh.vtu")
    ]


def test_preset_data_zip_separates_processed_raw_and_original_files(tmp_path):
    """Preset downloads use stable directories for each data stage."""
    processed = tmp_path / "processed" / "mesh.1.vtu"
    sidecar = tmp_path / "processed" / "mesh.tetgen.log"
    raw = tmp_path / "raw" / "interface_0.vtp"
    original = tmp_path / "raw" / "original_mesh_volume.vtu"
    for path, content in (
        (processed, "processed"),
        (sidecar, "log"),
        (raw, "raw"),
        (original, "original"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    archive_bytes = _preset_data_zip(
        "Case",
        processed_files=[processed, sidecar],
        raw_files=[raw],
        original_files=[original],
    )

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        assert set(archive.namelist()) == {
            "README.txt",
            "meshed_output/mesh.1.vtu",
            "meshed_output/mesh.tetgen.log",
            "raw_files/interface_0.vtp",
            "original_mesh/original_mesh_volume.vtu",
            "open_in_paraview.py",
        }
        assert archive.read("meshed_output/mesh.1.vtu") == b"processed"
        assert archive.read("raw_files/interface_0.vtp") == b"raw"
        assert archive.read("original_mesh/original_mesh_volume.vtu") == b"original"
        # The ParaView state script references each readable mesh by its
        # archive-relative path and skips non-mesh sidecars such as the TetGen log.
        state = archive.read("open_in_paraview.py").decode("utf-8")
        assert "'meshed_output/mesh.1.vtu'" in state
        assert "'raw_files/interface_0.vtp'" in state
        assert "'original_mesh/original_mesh_volume.vtu'" in state
        assert "mesh.tetgen.log" not in state
        # Pipeline names carry the preset, and level sets carry their layer number.
        assert "'Case - raw - level set layer 0'" in state
        assert "'Case - mesh - mesh.1'" in state
        assert "'Case - original - original_mesh_volume'" in state
        # White mesh edges and high-contrast categorical material coloring.
        assert "_EDGE_COLOR = [1.0, 1.0, 1.0]" in state
        assert '"Surface With Edges"' in state
        assert "InterpretValuesAsCategories" in state
        # The generated script must be valid Python.
        compile(state, "open_in_paraview.py", "exec")


def test_run_2d_polygon_preview_writes_line_vtp():
    """Pipeline polygon preview writes build_2d_poly_geometry output as VTP lines."""
    input_path = Path("tests/end_to_end/fixtures/2d/interface_0.vtp")

    output_path = _run_2d_polygon_preview([input_path], epsilon=1e-6)

    mesh = pv.read(output_path)
    assert output_path.suffix == ".vtp"
    assert mesh.n_points > 0
    assert mesh.n_cells > 0
    assert mesh.lines.size > 0


def test_run_pipeline_writes_meshed_3d_vtu_directly(tmp_path, monkeypatch):
    """A meshed 3D preview requests the final VTU directly."""
    input_path = Path("tests/end_to_end/fixtures/3d/interface_1.vtp")
    output_path = tmp_path / "mesh.vtu"
    commands: list[list[str]] = []

    def fake_run(command, **_kwargs: object):
        commands.append(command)
        out = Path(command[command.index("--out") + 1])
        out.write_text("tetgen", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("lsmesher.viewer.subprocess.run", fake_run)

    result = _run_pipeline(
        [input_path],
        epsilon=1e-6,
        output_format="vtu",
        run_mesher=True,
        output_path=output_path,
        decimation=DecimationOptions3D(target_faces=1400),
        mesher=MesherOptions(
            tetgen_quality_ratio=1.4,
            tetgen_min_dihedral=15.0,
            tetgen_max_volume=0.025,
            bottom_margin=0.2,
            seam_protection_rings=4,
        ),
    )

    assert result == output_path
    (command,) = commands
    assert command[:4] == [sys.executable, "-m", "lsmesher.cli", "mesh"]
    assert str(input_path) in command
    assert command[command.index("--format") + 1] == "vtu"
    assert command[command.index("--decimate-target-faces") + 1] == "1400"
    assert command[command.index("--tetgen-quality-ratio") + 1] == "1.4"
    assert command[command.index("--tetgen-min-dihedral") + 1] == "15.0"
    assert command[command.index("--tetgen-max-volume") + 1] == "0.025"
    assert command[command.index("--bottom-margin") + 1] == "0.2"
    assert command[command.index("--seam-protection-rings") + 1] == "4"


def test_run_pipeline_raises_on_subprocess_failure(tmp_path, monkeypatch):
    """A failing pipeline subprocess surfaces its output as an error."""
    input_path = Path("tests/end_to_end/fixtures/3d/interface_1.vtp")

    def fake_run(command, **_kwargs: object):
        return subprocess.CompletedProcess(
            command, 134, stdout="", stderr="malloc(): corrupted top size"
        )

    monkeypatch.setattr("lsmesher.viewer.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="exit code 134"):
        _run_pipeline(
            [input_path],
            epsilon=1e-6,
            output_format="vtp",
            run_mesher=True,
            output_path=tmp_path / "mesh.vtp",
        )


def test_viewer_import_keeps_pymeshlab_out_of_the_process():
    """The viewer must never load pymeshlab: its bundled Qt runtime binds
    thread-local state to short-lived Streamlit script threads and corrupts
    the heap, aborting the whole viewer process.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, lsmesher.viewer; sys.exit('pymeshlab' in sys.modules)",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_write_processed_mesh_returns_requested_meshed_3d_vtu(
    tmp_path,
    monkeypatch,
):
    """Processed mesh output is freshly written to a reachable directory."""
    input_path = Path("tests/end_to_end/fixtures/3d/interface_1.vtp")
    output_dir = tmp_path / "viewer_outputs" / "case" / "processed_mesh"
    output_path = output_dir / "mesh.vtu"

    def run_pipeline(input_paths, *, output_path, **_kwargs: object):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("tetgen", encoding="utf-8")
        return output_path

    monkeypatch.setattr("lsmesher.viewer._run_pipeline", run_pipeline)

    result = _write_processed_mesh_output(
        [input_path],
        options=ProcessedMeshOptions(
            epsilon=1e-6,
            output_format="vtu",
            run_mesher=True,
        ),
        output_dir=output_dir,
    )

    assert result == output_path


def test_processed_tetgen_log_path_strips_tetgen_suffixes():
    """The TetGen log is located next to any processed mesh output name."""
    assert _processed_tetgen_log_path(Path("/outputs/mesh.1.vtu")) == Path(
        "/outputs/mesh.tetgen.log"
    )
    assert _processed_tetgen_log_path(Path("/outputs/mesh.vtp")) == Path(
        "/outputs/mesh.tetgen.log"
    )


def test_write_processed_mesh_overwrites_previous_output(tmp_path, monkeypatch):
    """Processed mesh generation clears stale files before each run."""
    input_path = Path("tests/end_to_end/fixtures/3d/interface_1.vtp")
    output_dir = tmp_path / "viewer_outputs" / "case" / "processed_mesh"
    output_dir.mkdir(parents=True)
    stale_path = output_dir / "stale.vtp"
    stale_path.write_text("old", encoding="utf-8")

    def run_pipeline(input_paths, *, output_path, **_kwargs: object):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("mesh", encoding="utf-8")
        return output_path

    monkeypatch.setattr("lsmesher.viewer._run_pipeline", run_pipeline)

    result = _write_processed_mesh_output(
        [input_path],
        options=ProcessedMeshOptions(
            epsilon=1e-6,
            output_format="vtp",
            run_mesher=False,
            decimation=DecimationOptions3D(),
        ),
        output_dir=output_dir,
    )

    assert result == output_dir / "mesh.vtp"
    assert not stale_path.exists()


def test_preset_output_dir_uses_safe_preset_name(tmp_path):
    """Preset output directories are filesystem-safe and easy to find."""
    output_dir = _preset_output_dir(tmp_path, "Bosch Process 2D")

    assert output_dir.parent == tmp_path / "viewer_outputs"
    assert output_dir.name == "Bosch_Process_2D"


def test_write_2d_polygon_preview_overwrites_output(tmp_path):
    """Polygon preview writes fresh output into a reachable directory."""
    input_path = Path("tests/end_to_end/fixtures/2d/interface_0.vtp")
    output_dir = tmp_path / "viewer_outputs" / "case" / "pipeline_polygon"
    output_dir.mkdir(parents=True)
    stale_path = output_dir / "stale.vtp"
    stale_path.write_text("old", encoding="utf-8")

    result = _write_2d_polygon_preview_output(
        [input_path],
        epsilon=1e-6,
        output_dir=output_dir,
    )

    assert result == output_dir / "polygon.vtp"
    assert result.exists()
    assert not stale_path.exists()


def test_mesh_edge_coordinates_extracts_all_triangle_edges():
    """All-cell edge extraction includes triangle mesh edges for wireframe mode."""
    points = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [1.0, 1.0, 0.0],
        ],
    )
    faces = np.array([3, 0, 1, 2, 3, 1, 3, 2])
    mesh = pv.PolyData(points, faces)

    x_coords, y_coords, z_coords = _mesh_edge_coordinates(
        mesh,
        all_cell_edges=True,
    )

    assert x_coords
    assert y_coords
    assert z_coords
    assert x_coords.count(None) == 5


def test_pyvista_screenshot_writes_png():
    """PyVista renderer writes a server-side PNG for Streamlit display."""
    input_path = Path("tests/end_to_end/fixtures/2d/interface_0.vtp")

    output_path = _pyvista_screenshot(
        input_path,
        options=PyVistaPngOptions(
            show_edges=True,
            color="#8dd3ff",
            width=400,
            height=300,
        ),
    )

    assert output_path.suffix == ".png"
    assert output_path.stat().st_size > 0


def test_png_camera_uses_z_up_for_3d_mesh():
    """3D PNG previews use Z as the screen-up direction."""
    calls: list[tuple[str, object]] = []

    class Plotter:
        def view_vector(self, vector, viewup=None):
            calls.append(("view_vector", viewup))

        def view_xy(self):
            calls.append(("view_xy", None))

    mesh = pv.read("tests/end_to_end/fixtures/3d/interface_1.vtp")

    _set_png_camera(Plotter(), mesh)  # type: ignore[arg-type]

    assert calls == [("view_vector", (0.0, 0.0, 1.0))]


def test_png_camera_keeps_flat_mesh_top_down():
    """Flat 2D PNG previews keep the previous XY camera."""
    calls: list[str] = []

    class Plotter:
        def view_vector(self, vector, viewup=None):
            calls.append("view_vector")

        def view_xy(self):
            calls.append("view_xy")

    mesh = pv.read("tests/end_to_end/fixtures/2d/interface_0.vtp")

    _set_png_camera(Plotter(), mesh)  # type: ignore[arg-type]

    assert calls == ["view_xy"]
