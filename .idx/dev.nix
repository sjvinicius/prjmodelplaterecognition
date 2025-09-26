{ pkgs, ... }: {
  channel = "stable-24.05";

  packages = [
    pkgs.python3
    pkgs.glib              # fornece libgthread-2.0.so.0
    pkgs.libGL
    pkgs.libGLU
    pkgs.mesa
    pkgs.mesa.dev

    pkgs.xorg.libSM
    pkgs.xorg.libXrender
    pkgs.xorg.libXext
  ];

  idx = {
    extensions = [
      "ms-python.python"
      "rangav.vscode-thunder-client"
    ];

    workspace = {
      onCreate = {
        install =
          "python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt";
        default.openFiles = [ "README.md" "src/index.html" "main.py" ];
      };

      onStart = {
        run-server = "./devserver.sh";
      };
    };
  };
}
