#!/bin/sh
set -eu
python3 "$1" "$PWD/pcr.yaml" "$PWD/event.yaml"
