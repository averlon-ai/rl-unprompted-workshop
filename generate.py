#!/usr/bin/env python3
"""STAGE 1 of 2: send the eval-set prompts to the checkpoints on the cynos endpoint and save their responses.
Nothing is judged here; judge.py (stage 2) labels these responses afterwards.

    python generate.py                           # all five checkpoints, 50 held-out prompts per class
    python generate.py --models base,m3 --per-class 20
    python generate.py --all                     # the full held-out set (221 + 249 prompts per checkpoint)
    python generate.py --check                   # connectivity only: one short answer from each checkpoint

Output: results/<UTC time>/responses.jsonl  (one row per (checkpoint, prompt): model, id, target, prompt, finish,
response) plus generate.json with the arguments. Needs the endpoint key in CYNOS_API_KEY (asked for if missing) and
the dataset (data/build_data.py; run automatically when it is missing).
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import avn_client as A  # noqa: E402

CHECK_QUESTION = "In two sentences, what is the MITRE ATT&CK technique T1003 (OS Credential Dumping)?"


def ensure_data():
    if os.path.isfile(os.path.join(HERE, "data", "eval", "policy_unblock.jsonl")):
        return
    print("dataset missing: running data/build_data.py")
    try:
        subprocess.run([sys.executable, os.path.join(HERE, "data", "build_data.py")], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        sys.exit("could not build the validation set: it is rebuilt from its upstream sources by data/build_data.py "
                 "(needs network access once; see data/DATA_PROVENANCE.md).")


def check(client, models):
    """One short completion per checkpoint. The endpoint offers no model discovery, so this is the connectivity test."""
    print(f"endpoint: {A.BASE_URL}")
    ok, msg = A.check_key(client)                # the key once, before the five models
    print(("key: " + msg) if ok else ("key REJECTED: " + msg))
    if not ok:
        return False
    for m in models:
        t = time.time()
        try:
            fr, text = A.ask(client, m, CHECK_QUESTION, 160)
            print(f"  {A.model_id(m):<12} ok    {fr:<7} {time.time() - t:5.1f}s  {' '.join(text[:110].split())}")
        except Exception as e:                       # noqa: BLE001
            ok = False
            print(f"  {A.model_id(m):<12} FAIL  {type(e).__name__}: {str(e)[:140]}")
    return ok


def save_rows(rows, out_dir, name="responses.jsonl"):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


def run_generate(client, models, per_class=50, seed=0, workers=16, max_tokens=2048,
                 out_root=os.path.join(HERE, "results")):
    """Sample the held-out prompts, generate one response per (checkpoint, prompt), save. Returns the output dir."""
    ensure_data()
    prompts = A.sample_heldout(A.load_heldout(), per_class, seed)
    print(f"generating: {len(prompts)} held-out prompts x {len(models)} checkpoints on {A.BASE_URL} ...")
    t0 = time.time()
    rows = A.generate(client, models, prompts, max_tokens=max_tokens, workers=workers)
    out = os.path.join(out_root, datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    save_rows(rows, out)
    json.dump({"stage": "generate", "endpoint": A.BASE_URL, "models": [A.model_id(m) for m in models],
               "per_class": per_class, "seed": seed, "max_tokens": max_tokens, "n_rows": len(rows),
               "seconds": round(time.time() - t0, 1)}, open(os.path.join(out, "generate.json"), "w"), indent=1)
    bad = sum(1 for r in rows if "response" not in r)
    print(f"saved {len(rows)} responses -> {out}/responses.jsonl" + (f"  ({bad} failed; see 'error')" if bad else ""))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=",".join(A.MODELS),
                    help="comma-separated model ids (default: all five); short aliases base,m1,m2,m3,mc also work")
    ap.add_argument("--per-class", type=int, default=50, help="held-out prompts per class (default 50)")
    ap.add_argument("--all", action="store_true", help="the full held-out set")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--check", action="store_true", help="connectivity only")
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    args = ap.parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    client = A.get_client()
    ok = check(client, models)
    if args.check:
        sys.exit(0 if ok else 1)
    if not ok:
        sys.exit("endpoint check failed: fix the key or the model names above before generating")
    run_generate(client, models, None if args.all else args.per_class, args.seed, args.workers, args.max_tokens, args.out)


if __name__ == "__main__":
    main()
