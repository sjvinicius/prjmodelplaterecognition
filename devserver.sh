#!/bin/sh
# python3 -m venv .venv
# rm -rf .venv310
# python3.10 -m venv .venv310
# source .venv/bin/activate
# source .venv310/bin/activate
# source ./venv/Scripts/activate
# source ./venv310/Scripts/activate

pip install --upgrade pip
pip install -r requirements.txt
# Necessário instalar o FFMPEG para habilitar o funcionamento de conexão em câmeras RTSP.

# winget install Gyan.FFmpeg

# sudo apt update
# sudo apt install ffmpeg -y

# python3 -u -m flask --app main run --debug
# py -u -m flask --app main run --debug

python -u -m flask --app main run --debug