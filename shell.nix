{
  pkgs ? import <nixpkgs> { },
}:

pkgs.mkShell {
  name = "dev-environment";
  buildInputs = with pkgs; [
    ansible
    ansible-lint
    uv # https://nixos.org/manual/nixpkgs/unstable/#sec-uv
    nodejs_24
    just
    gh

    gcc
    pkg-config
    libvirt
    python314
  ];

  shellHook = ''
    export LD_LIBRARY_PATH=${pkgs.libvirt}/lib:$LD_LIBRARY_PATH
    export UV_PYTHON_PREFERENCE="system"
  '';
}
