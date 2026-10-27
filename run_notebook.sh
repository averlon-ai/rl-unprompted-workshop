#!/usr/bin/env bash
# Install what the notebook needs and open it in JupyterLab, from a fresh checkout.
#
#   bash run_notebook.sh                 # venv, dependencies, dataset, then JupyterLab on notebooks/livetest.ipynb
#   bash run_notebook.sh --setup-only    # everything except launching (for coding agents and CI)
#   bash run_notebook.sh --port 8890     # any other argument goes to `jupyter lab`
#
# On a remote machine add --no-browser and open the printed URL through an SSH tunnel
# (ssh -L 8888:localhost:8888 <host>). The endpoint key can be entered in the notebook's first cell, or beforehand
# with  bash save_key.sh.  Everything installs into ./.venv (gitignored); re-running is safe and fast.
set -euo pipefail
cd "$(dirname "$0")"

SETUP_ONLY=0; ARGS=()
for a in "$@"; do
  if [ "$a" = "--setup-only" ]; then SETUP_ONLY=1; else ARGS+=("$a"); fi
done

if [ ! -x .venv/bin/python ]; then
  echo "creating .venv"
  python3 -m venv .venv
fi
PY=.venv/bin/python
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r requirements.txt jupyterlab
# the kernel the notebook runs on is this venv; registered inside the venv so nothing outside it changes
"$PY" -m ipykernel install --sys-prefix --name python3 --display-name "Python 3 (livetest)" >/dev/null

if [ ! -f data/eval/policy_unblock.jsonl ]; then
  echo "building the validation set from its upstream sources (once; see data/DATA_PROVENANCE.md)"
  "$PY" data/build_data.py
fi

if [ ! -f .env ]; then
  echo "note: no .env yet. The notebook's first cell asks for the cynos API key and the judge model; or run: bash save_key.sh"
fi

if [ "$SETUP_ONLY" = "1" ]; then
  echo "setup complete: .venv ready, dataset built. Launch with:  .venv/bin/jupyter lab notebooks/livetest.ipynb"
  exit 0
fi
exec .venv/bin/jupyter lab notebooks/livetest.ipynb ${ARGS[@]+"${ARGS[@]}"}
