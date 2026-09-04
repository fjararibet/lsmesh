{
  description = "lsmesher Streamlit viewer";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    cpm-cmake = {
      url = "github:cpm-cmake/CPM.cmake/v0.42.0";
      flake = false;
    };
    package-project = {
      url = "github:TheLartians/PackageProject.cmake/v1.13.0";
      flake = false;
    };
    pybind11-source = {
      url = "github:pybind/pybind11/v3.0.1";
      flake = false;
    };
    viennacore = {
      url = "github:ViennaTools/ViennaCore/v2.2.1";
      flake = false;
    };
    viennahrle = {
      url = "github:ViennaTools/ViennaHRLE/v1.1.2";
      flake = false;
    };
    viennals = {
      url = "github:ViennaTools/ViennaLS/v5.8.5";
      flake = false;
    };
    viennaray = {
      # Parent of the 2026-08-20 Source API split; current ViennaPS still uses
      # getOriginAndDirection and does not compile against that newer commit.
      url = "github:ViennaTools/ViennaRay/6cd664ceddebfa2ef67bda944e68886d880f889e";
      flake = false;
    };
    viennacs = {
      url = "github:ViennaTools/ViennaCS/v2.1.2";
      flake = false;
    };
    viennaps = {
      url = "github:ViennaTools/ViennaPS";
      flake = false;
    };
  };

  outputs = inputs@{ nixpkgs, ... }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      perSystem = system:
        let
          pkgs = import nixpkgs {
            inherit system;
            config.allowUnfree = true;
          };
          runtimeLibs = with pkgs; [
            libx11
            libxext
            libxrender
            libxcomposite
            libxdamage
            libxfixes
            libxtst
            libxcb
            libxshmfence
            libxi
            libxcursor
            libxrandr
            libxinerama
            xorgproto
            libGL
            libGLU
            mesa
            vtk
            e2fsprogs
            gmp
            p11-kit
            glib
            nss
            nspr
            atk
            at-spi2-atk
            cups
            dbus
            gtk3
            pango
            cairo
            expat
            libxkbcommon
            libdrm
            libgbm
            alsa-lib
            tetgen
          ];
          devTools = with pkgs; [
            cmake
            pkg-config
            uv
          ];
          # CUDA 12.8 is the oldest toolkit with Blackwell (sm_120) support and
          # is compatible with a wider range of host NVIDIA drivers.
          cudaPackages = pkgs.cudaPackages_12_8;
          cudaTools = with cudaPackages; [
            cuda_cudart
            cuda_nvcc
            libcublas
            libcusparse
          ];
          libraryPath = pkgs.lib.makeLibraryPath runtimeLibs;
          cudaLibraryPath = pkgs.lib.makeLibraryPath cudaTools;
          hostCudaDriver =
            if system == "x86_64-linux" then
              "/usr/lib/x86_64-linux-gnu/libcuda.so.1"
            else
              "/usr/lib/aarch64-linux-gnu/libcuda.so.1";
          includePath = pkgs.lib.makeSearchPathOutput "dev" "include" runtimeLibs;
          cudaTestSource = pkgs.writeText "lsmesher-cuda-test.cu" ''
            #include <cuda_runtime.h>
            #include <dlfcn.h>
            #include <link.h>
            #include <iostream>

            int main() {
              void* driver = dlopen("libcuda.so.1", RTLD_NOW | RTLD_LOCAL);
              if (driver == nullptr) {
                std::cerr << "Unable to load libcuda.so.1: " << dlerror() << '\n';
                return 1;
              }
              link_map* driver_map = nullptr;
              if (dlinfo(driver, RTLD_DI_LINKMAP, &driver_map) == 0 && driver_map != nullptr) {
                std::cout << "CUDA driver library: " << driver_map->l_name << '\n';
              }
              using DriverGetVersion = int (*)(int*);
              auto driver_get_version = reinterpret_cast<DriverGetVersion>(
                  dlsym(driver, "cuDriverGetVersion"));
              int driver_version = 0;
              if (driver_get_version != nullptr && driver_get_version(&driver_version) == 0) {
                std::cout << "CUDA driver API: " << driver_version / 1000 << '.'
                          << (driver_version % 1000) / 10 << '\n';
              }

              int count = 0;
              const cudaError_t status = cudaGetDeviceCount(&count);
              if (status != cudaSuccess) {
                std::cerr << "CUDA error: " << cudaGetErrorString(status) << '\n';
                return static_cast<int>(status);
              }
              std::cout << "CUDA devices: " << count << '\n';
              for (int device = 0; device < count; ++device) {
                cudaDeviceProp properties{};
                if (cudaGetDeviceProperties(&properties, device) != cudaSuccess) {
                  return 1;
                }
                std::cout << device << ": " << properties.name << " (sm_"
                          << properties.major << properties.minor << ")\n";
              }
              return count > 0 ? 0 : 1;
            }
          '';
          cudaTest = pkgs.stdenv.mkDerivation {
            pname = "lsmesher-cuda-test";
            version = "1";
            dontUnpack = true;
            nativeBuildInputs = [ cudaPackages.cuda_nvcc pkgs.makeWrapper ];
            buildInputs = [ cudaPackages.cuda_cudart ];
            buildPhase = ''
              runHook preBuild
              nvcc -arch=sm_120 ${cudaTestSource} -o lsmesher-cuda-test
              runHook postBuild
            '';
            installPhase = ''
              runHook preInstall
              install -Dm755 lsmesher-cuda-test $out/bin/lsmesher-cuda-test
              runHook postInstall
            '';
            postFixup = ''
              wrapProgram $out/bin/lsmesher-cuda-test \
                --set LD_PRELOAD ${hostCudaDriver}
            '';
          };
          python = pkgs.python312;
          withPinnedCpm = name: source: pkgs.runCommand "${name}-source" { } ''
            cp -R ${source} $out
            chmod -R u+w $out
            if [ -e $out/cmake/cpm.cmake ]; then
              cp ${inputs.cpm-cmake}/cmake/CPM.cmake $out/cmake/cpm.cmake
            fi
          '';
          viennacoreSource = withPinnedCpm "viennacore" inputs.viennacore;
          viennahrleSource = withPinnedCpm "viennahrle" inputs.viennahrle;
          viennalsSource = withPinnedCpm "viennals" inputs.viennals;
          viennaraySource = withPinnedCpm "viennaray" inputs.viennaray;
          viennacsSource = withPinnedCpm "viennacs" inputs.viennacs;
          viennapsSource = withPinnedCpm "viennaps" inputs.viennaps;
          cpmSourceArgs = [
            "-DCPM_PackageProject_SOURCE=${inputs.package-project}"
            "-DCPM_ViennaCore_SOURCE=${viennacoreSource}"
            "-DCPM_ViennaHRLE_SOURCE=${viennahrleSource}"
            "-DCPM_ViennaRay_SOURCE=${viennaraySource}"
            "-DCPM_ViennaCS_SOURCE=${viennacsSource}"
            "-DCPM_ViennaLS_SOURCE=${viennalsSource}"
            "-DCPM_pybind11_SOURCE=${inputs.pybind11-source}"
          ];
          viennalsCuda = python.pkgs.buildPythonPackage {
            pname = "viennals-cuda";
            version = "5.8.5";
            pyproject = true;
            src = viennalsSource;

            postPatch = ''
              substituteInPlace pyproject.toml \
                --replace-fail 'scikit-build-core>=0.12.2' 'scikit-build-core>=0.11.6'
              cp ${inputs.cpm-cmake}/cmake/CPM.cmake cmake/cpm.cmake
            '';

            build-system = with python.pkgs; [
              scikit-build-core
              pybind11
            ];
            nativeBuildInputs = [
              pkgs.cmake
              pkgs.ninja
              pkgs.pkg-config
              cudaPackages.cuda_nvcc
            ];
            buildInputs = [
              pkgs.vtk
              cudaPackages.cuda_cudart
              cudaPackages.libcusparse
            ];
            pypaBuildFlags = map (arg: "-Ccmake.args=${arg}") (
              cpmSourceArgs
              ++ [
                "-DVIENNALS_BUILD_PYTHON=ON"
                "-DVIENNALS_USE_GPU=ON"
                "-DCMAKE_CUDA_ARCHITECTURES=120"
              ]
            );
            dontUseCmakeConfigure = true;
            doCheck = false;
          };
          viennapsCuda = python.pkgs.buildPythonPackage {
            pname = "viennaps-cuda-oxidation";
            version = "4.7.0";
            pyproject = true;
            src = viennapsSource;

            postPatch = ''
              substituteInPlace pyproject.toml \
                --replace-fail 'scikit-build-core>=0.12.2' 'scikit-build-core>=0.11.6'
              cp ${inputs.cpm-cmake}/cmake/CPM.cmake cmake/cpm.cmake
              mkdir -p nix-deps
              cp -R ${viennalsSource} nix-deps/viennals
              cp -R ${viennacsSource} nix-deps/viennacs
              chmod -R u+w nix-deps
              sed -i '1a set(CPM_ViennaLS_SOURCE "''${CMAKE_CURRENT_SOURCE_DIR}/nix-deps/viennals" CACHE PATH "" FORCE)\nset(CPM_ViennaCS_SOURCE "''${CMAKE_CURRENT_SOURCE_DIR}/nix-deps/viennacs" CACHE PATH "" FORCE)' CMakeLists.txt
              # The oxidation solver lives in ViennaLS. Enable that CUDA
              # backend without enabling ViennaPS's separate ray-tracing GPU
              # backend and its PTX/OptiX dependency graph.
              substituteInPlace CMakeLists.txt \
                --replace-fail \
                  '"VIENNALS_VTK_RENDERING ''${VIENNAPS_VTK_RENDERING}" "VIENNALS_USE_GPU ''${VIENNAPS_USE_GPU}"' \
                  '"VIENNALS_VTK_RENDERING ''${VIENNAPS_VTK_RENDERING}" "VIENNALS_USE_GPU ON"'
            '';
            build-system = with python.pkgs; [
              scikit-build-core
              pybind11
            ];
            nativeBuildInputs = [
              pkgs.cmake
              pkgs.ninja
              pkgs.pkg-config
              cudaPackages.cuda_nvcc
            ];
            buildInputs = [
              pkgs.embree
              pkgs.tbb
              pkgs.vtk
              cudaPackages.cuda_cudart
              cudaPackages.libcusparse
            ];
            dependencies = [ viennalsCuda ];
            pypaBuildFlags = map (arg: "-Ccmake.args=${arg}") (
              cpmSourceArgs
              ++ [
                "-DVIENNAPS_BUILD_PYTHON=ON"
                "-DVIENNAPS_USE_GPU=OFF"
                "-DCMAKE_CUDA_ARCHITECTURES=120"
              ]
            );
            dontUseCmakeConfigure = true;
            doCheck = false;
          };
          cudaPythonPath = pkgs.lib.makeSearchPath python.sitePackages [
            viennalsCuda
            viennapsCuda
          ];
          cudaPython = python.withPackages (_: [
            viennalsCuda
            viennapsCuda
          ]);
          triangleCc = pkgs.writeShellApplication {
            name = "cc";
            runtimeInputs = [ pkgs.stdenv.cc ];
            text = ''
              exec ${pkgs.stdenv.cc}/bin/cc -std=gnu89 "$@"
            '';
          };
          mkLsmesherApp = name: command: pkgs.writeShellApplication {
            inherit name;
            runtimeInputs = [
              triangleCc
              pkgs.stdenv.cc
              pkgs.tetgen
              pkgs.uv
            ];
            text = ''
              export CMAKE_PREFIX_PATH="${pkgs.vtk}:''${CMAKE_PREFIX_PATH:-}"
              export CPATH="${includePath}:''${CPATH:-}"
              export LD_LIBRARY_PATH="${libraryPath}:''${LD_LIBRARY_PATH:-}"
              export LIBRARY_PATH="${libraryPath}:''${LIBRARY_PATH:-}"
              export PYVISTA_OFF_SCREEN="''${PYVISTA_OFF_SCREEN:-true}"
              exec uv run --frozen ${command} "$@"
            '';
          };
          runViewer = mkLsmesherApp "lsmesher-viewer" "--extra viewer lsmesher-viewer";
          runCli = mkLsmesherApp "lsmesher" "lsmesher";
          runDocs = pkgs.writeShellApplication {
            name = "lsmesher-docs";
            runtimeInputs = [ pkgs.uv ];
            text = ''
              exec uvx --from mkdocs --with mkdocs-material --with "mkdocstrings[python]" --with ruff mkdocs serve "$@"
            '';
          };
        in
        {
          apps.default = {
            type = "app";
            program = "${runViewer}/bin/lsmesher-viewer";
            meta.description = "Launch the lsmesher Streamlit viewer";
          };
          apps.viewer = {
            type = "app";
            program = "${runViewer}/bin/lsmesher-viewer";
            meta.description = "Launch the lsmesher Streamlit viewer";
          };
          apps.cli = {
            type = "app";
            program = "${runCli}/bin/lsmesher";
            meta.description = "Run the lsmesher command-line interface";
          };
          apps.docs = {
            type = "app";
            program = "${runDocs}/bin/lsmesher-docs";
            meta.description = "Serve the documentation site locally";
          };
          apps.cuda-test = {
            type = "app";
            program = "${cudaTest}/bin/lsmesher-cuda-test";
            meta.description = "Verify that CUDA can access the NVIDIA GPU";
          };

          packages.cuda-test = cudaTest;
          packages.viennals-cuda = viennalsCuda;
          packages.viennaps-cuda = viennapsCuda;

          devShells.default = pkgs.mkShell {
            packages = [ triangleCc ] ++ runtimeLibs ++ devTools;

            shellHook = ''
              export CMAKE_PREFIX_PATH="${pkgs.vtk}:$CMAKE_PREFIX_PATH"
              export CPATH="${includePath}:$CPATH"
              export LD_LIBRARY_PATH="${libraryPath}:$LD_LIBRARY_PATH"
              export LIBRARY_PATH="${libraryPath}:$LIBRARY_PATH"
              if [ -n "$DISPLAY" ]; then
                xset fp+ ${pkgs.font-misc-misc}/share/fonts/X11/misc 2>/dev/null || true
                xset fp rehash 2>/dev/null || true
              fi
              echo "lsmesher development environment loaded"
              echo "VTK path: ${pkgs.vtk}"
            '';
          };

          devShells.cuda = pkgs.mkShell {
            packages = [
              triangleCc
              cudaPython
            ] ++ runtimeLibs ++ devTools ++ cudaTools;

            shellHook = ''
              export CMAKE_PREFIX_PATH="${pkgs.vtk}:$CMAKE_PREFIX_PATH"
              export CPATH="${includePath}:$CPATH"
              export LD_LIBRARY_PATH="${libraryPath}:${cudaLibraryPath}:$LD_LIBRARY_PATH"
              export LIBRARY_PATH="${libraryPath}:${cudaLibraryPath}:$LIBRARY_PATH"

              # NVIDIA Blackwell / GeForce RTX 50-series architecture.
              export CMAKE_CUDA_ARCHITECTURES="''${CMAKE_CUDA_ARCHITECTURES:-120}"
              export CUDAARCHS="''${CUDAARCHS:-120}"
              export PYTHONPATH="${cudaPythonPath}:''${PYTHONPATH:-}"
              export UV_PYTHON="${cudaPython}/bin/python"
              export LSMESHER_CUDA_DRIVER="${hostCudaDriver}"
              # Load only the host driver itself. Adding the host library
              # directory would also expose its glibc to Nix programs.
              export LD_PRELOAD="${hostCudaDriver}''${LD_PRELOAD:+:$LD_PRELOAD}"

              if [ -n "$DISPLAY" ]; then
                xset fp+ ${pkgs.font-misc-misc}/share/fonts/X11/misc 2>/dev/null || true
                xset fp rehash 2>/dev/null || true
              fi
              echo "lsmesher CUDA development environment loaded"
              echo "CUDA toolkit: ${cudaPackages.cuda_nvcc}"
              echo "CUDA architecture: $CMAKE_CUDA_ARCHITECTURES"
            '';
          };
        };
    in
    {
      apps = forAllSystems (system: (perSystem system).apps);
      devShells = forAllSystems (system: (perSystem system).devShells);
      packages = forAllSystems (system: (perSystem system).packages);
    };
}
