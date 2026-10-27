#!/usr/bin/env bash
# Store your cynos API key, and the judge model for stage 2, in .env: the one place every script and the notebook
# read them from (gitignored, mode 600). The key is typed hidden, tested against the endpoint with one short
# request, and written only if the endpoint accepts it; nothing prints it. Run again any time to replace a value.
#
#   bash save_key.sh
set -euo pipefail
cd "$(dirname "$0")"
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python     # the project venv when one exists
"$PY" -c "import openai" 2>/dev/null || "$PY" -m pip install -q -r requirements.txt
read -rsp "cynos API key (starts with sk-cy-, typed hidden): " NEW_KEY; echo
read -rp "judge model for stage 2, served on the same endpoint (Enter keeps the current one): " NEW_JUDGE
NEW_KEY="$NEW_KEY" NEW_JUDGE="$NEW_JUDGE" "$PY" - <<'PY'
import os, sys
import avn_client as A
key, judge = os.environ["NEW_KEY"].strip(), os.environ["NEW_JUDGE"].strip()
if not key:
    sys.exit("no key typed; nothing saved")
ok, msg = A.check_key(A.get_client(key))
if not ok:
    sys.exit(f"not saved: {msg}")
values = {"CYNOS_API_KEY": key}
if judge:
    values["AVN_JUDGE_MODEL"] = judge
path = A.save_env(**values)
print(f"{msg}; saved to {os.path.relpath(path)} (mode 600)")
if not (judge or A.JUDGE_MODEL):
    print("judge model not set yet: run again, or put AVN_JUDGE_MODEL=<model> in .env before stage 2")
PY
