#!/usr/bin/env bash
# One command from a fresh checkout to a scored result: a venv, the dependencies, the validation set (built from its
# upstream sources), an endpoint check, then stage 1 (generate) and stage 2 (judge). Any extra arguments go to
# run_tests.py (e.g. --models base,m3 --per-class 20).
#
# Before running: log in to cynos, create an API key, then  bash save_key.sh  (or cp .env.example .env and fill it).
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f .env ]; then
  echo "no .env found. Log in to cynos, create an API key, then:  bash save_key.sh   (or cp .env.example .env and fill it in)"
  exit 1
fi
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt
.venv/bin/python data/build_data.py || { echo "could not build the validation set (it is rebuilt from its upstream sources: see data/DATA_PROVENANCE.md)"; exit 1; }
.venv/bin/python run_tests.py "$@"      # checks the key and the five checkpoints first, then stage 1 and stage 2
