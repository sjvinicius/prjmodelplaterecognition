{ pkgs, ... }: {
  channel = "stable-24.05";
  packages = [
    pkgs.python3
    pkgs.apt
    pkgs.mesa # bibliotecas mesa básicas
    pkgs.mesa.dev # arquivos de desenvolvimento (inclui libGL.so)
    pkgs.libGL # garante libGL.so.1 disponível
  ];
  idx = {
    extensions = [ "ms-python.python" "rangav.vscode-thunder-client" ];
    workspace = {
      onCreate = {
        install =
          "python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt";
        default.openFiles = [ "README.md" "src/index.html" "main.py" ];
      };
      onStart = { run-server = "./devserver.sh"; };
    };
  };
}
