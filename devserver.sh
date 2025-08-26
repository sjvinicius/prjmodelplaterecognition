#!/bin/sh
#python3 -m venv .venv
source .venv/bin/activate
python -u -m flask --app main run --debug