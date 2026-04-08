#!/bin/sh
# python3 -m venv .venv
# python3.10 -m venv .venv310
# source .venv/bin/activate
# source .venv310/bin/activate
# source ./venv/Scripts/activate
# source ./venv310/Scripts/activate

# Necessário instalar o FFMPEG para habilitar o funcionamento de conexão em câmeras RTSP.
# Para parar o warning instalar o ccache 
# Flask==2.3.3
# numpy==1.24.4
# opencv-python==4.6.0.66
# paddlepaddle==2.6.2
# paddleocr==2.7.0.3
# ultralytics==8.0.230
# python-dotenv==1.0.1
# cryptography==42.0.5
# imgaug==0.4.0
# scipy==1.10.1
# requests==2.31.0

# python3 -u -m flask --app main run --debug
# py -u -m flask --app main run --debug

python -u -m flask --app main run --debug