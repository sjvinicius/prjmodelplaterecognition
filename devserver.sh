#!/bin/sh
python3 -m venv .venv
source .venv/bin/activate
#pip install paddleocr --no-deps
pip install flask ultralytics opencv-python numpy python-dotenv requests cryptography paddleocr paddlepaddle
# source ./venv/Scripts/activate
# python3 -u -m flask --app main run --debug
#py -u -m flask --app main run --debug
python -u -m flask --app main run --debug