{
  description = "Krux-installer flake";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python313;
      in {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            python
            python.pkgs.pip
            pkgs.uv
            pkgs.ffmpeg
            pkgs.stdenv.cc.cc.lib
          ];
          shellHook = ''
            export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib:$LD_LIBRARY_PATH"
            if [ ! -d ".venv" ]; then
              python -m venv .venv
            fi
            source .venv/bin/activate
            pip install -r requirements.txt
          '';
        };
      }
    );
}