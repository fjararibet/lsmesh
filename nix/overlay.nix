final: prev:
{
  pythonPackagesExtensions = prev.pythonPackagesExtensions ++ [
    (pythonFinal: pythonPrev:
      let
        lock = builtins.fromTOML (builtins.readFile ../uv.lock);
        # These upstream projects publish wheels but no source distributions.
        viennaWheel = name: dependencies:
          let
            package = final.lib.findFirst (p: p.name == name)
              (throw "${name} is missing from uv.lock") lock.package;
            tag = "cp${builtins.replaceStrings [ "." ] [ "" ] pythonFinal.python.pythonVersion}";
            wheel = final.lib.findFirst
              (w: final.lib.hasInfix "-${tag}-${tag}-manylinux_" w.url
                && final.lib.hasSuffix "_x86_64.whl" w.url)
              (throw "${name}: no locked Linux wheel for ${tag}") package.wheels;
          in
          pythonFinal.buildPythonPackage {
            pname = name;
            inherit (package) version;
            format = "wheel";
            src = final.fetchurl { inherit (wheel) url hash; };
            nativeBuildInputs = [ final.autoPatchelfHook ];
            buildInputs = [ final.stdenv.cc.cc.lib final.zlib final.libx11 final.libxext ];
            inherit dependencies;
            pythonImportsCheck = [ name ];
            meta.platforms = [ "x86_64-linux" ];
          };
      in
      {
        # Nixpkgs builds PyMeshLab with CMake, which omits Python distribution
        # metadata. Supply it so dependency checks and importlib.metadata work.
        pymeshlab = pythonPrev.pymeshlab.overridePythonAttrs (old: {
          postInstall = (old.postInstall or "") + ''
            install -Dm644 ${final.writeText "pymeshlab-METADATA" ''
              Metadata-Version: 2.1
              Name: pymeshlab
              Version: ${old.version}
              Requires-Dist: numpy
            ''} "$out/${pythonFinal.python.sitePackages}/pymeshlab-${old.version}.dist-info/METADATA"
          '';
        });
        viennals = viennaWheel "viennals" [ ];
        viennaps = viennaWheel "viennaps" [ pythonFinal.viennals ];
        lsmesh = pythonFinal.callPackage ./package.nix { };
      })
  ];
}
