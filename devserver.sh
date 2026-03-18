#!/bin/sh
#python3 -m venv .venv
# source .venv/bin/activate
source ./venv/Scripts/activate
# python3 -u -m flask --app main run --debug
py -u -m flask --app main run --debug
