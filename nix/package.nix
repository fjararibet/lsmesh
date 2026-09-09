{
  lib,
  buildPythonPackage,
  python,
  hatchling,
  numpy,
  scipy,
  vtk,
  pymeshlab,
  viennals,
  viennaps,
  plotly,
  pyvista,
  streamlit,
  libx11,
  tetgen,
  pkgs,
}:
let
  project = (builtins.fromTOML (builtins.readFile ../pyproject.toml)).project;
in
buildPythonPackage {
  pname = project.name;
  inherit (project) version;
  pyproject = true;
  src = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      ../pyproject.toml
      ../README.md
      ../hatch_build_triangle.py
      (lib.fileset.fileFilter (file: file.hasExt "py") ../src/lsmesh)
      ../vendor/triangle
    ];
  };
  build-system = [ hatchling ];
  nativeBuildInputs = [ pkgs.uv ];
  buildInputs = [ libx11 ];
  dependencies = [ numpy scipy vtk pymeshlab viennals viennaps ];
  optional-dependencies.viewer = [ plotly pyvista streamlit ];

  # Nixpkgs supplies a coherent scientific Python stack; uv retains the
  # project's tighter pins for development outside the packaged environment.
  pythonRelaxDeps = [ "scipy" "vtk" ];

  # Library callers also need TetGen, even when PATH contains no Nix tools.
  postPatch = ''
    substituteInPlace src/lsmesh/meshing.py \
      --replace-fail 'shutil.which("tetgen")' '"${lib.getExe tetgen}"'
  '';
  buildPhase = ''
    runHook preBuild
    export UV_PYTHON_DOWNLOADS=never
    UV_CACHE_DIR="$TMPDIR/uv-cache" uv build --python ${python.interpreter} --offline --no-build-isolation --wheel
    runHook postBuild
  '';
  pythonImportsCheck = [ "lsmesh" "lsmesh.build" "lsmesh.errors" "lsmesh.geometry" "lsmesh.options" ];
  meta = {
    inherit (project) description;
    homepage = project.urls.Repository;
    mainProgram = "lsmesh";
    platforms = [ "x86_64-linux" ];
  };
}
