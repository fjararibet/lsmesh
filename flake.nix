{
  description = "lsmesher Streamlit viewer";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { nixpkgs, ... }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      perSystem = system:
        let
          pkgs = import nixpkgs { inherit system; };
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
          libraryPath = pkgs.lib.makeLibraryPath runtimeLibs;
          includePath = pkgs.lib.makeSearchPathOutput "dev" "include" runtimeLibs;
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
        };
    in
    {
      apps = forAllSystems (system: (perSystem system).apps);
      devShells = forAllSystems (system: (perSystem system).devShells);
    };
}
