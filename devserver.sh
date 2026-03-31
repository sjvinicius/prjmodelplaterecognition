#!/bin/sh
# python3 -m venv .venv
# source .venv/bin/activate
# source .venv310/bin/activate
#pip install paddleocr --no-deps
# pip uninstall -y opencv-python paddleocr paddlepaddle
# pip uninstall -y numpy
# pip install numpy==1.23.5
# pip install --no-cache-dir paddlepaddle==2.6.1
# pip install --no-cache-dir paddleocr==2.7.0.3
# pip install flask ultralytics opencv-python numpy python-dotenv requests cryptography
# pip install paddlepaddle==2.6.1
# pip install paddleocr==2.7.0.3
# source ./venv/Scripts/activate
# python3 -u -m flask --app main run --debug
#py -u -m flask --app main run --debug

python -u -m flask --app main run --debug