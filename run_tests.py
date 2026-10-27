#!/usr/bin/env python3
"""Both stages in one command: generate (stage 1) then judge (stage 2) on the cynos endpoint.

    python run_tests.py                          # all five checkpoints, 50 held-out prompts per class
    python run_tests.py --models base,m3 --per-class 20
    python run_tests.py --all                    # the full held-out set (221 + 249 prompts per checkpoint)
    python run_tests.py --check                  # connectivity only: one short answer from each checkpoint

Same flags as generate.py, plus --judge-model. The two stages can also be run separately (generate.py, judge.py);
the notebook drives the same functions. Results: results/<UTC time>/{responses.jsonl, labels.jsonl, metrics.json,
report.md}.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import avn_client as A  # noqa: E402
import generate as G    # noqa: E402
import judge as J       # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=",".join(A.MODELS),
                    help="comma-separated model ids (default: all five); short aliases base,m1,m2,m3,mc also work")
    ap.add_argument("--per-class", type=int, default=50, help="held-out prompts per class (default 50)")
    ap.add_argument("--all", action="store_true", help="the full held-out set")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--judge-model", default=None, help="judge model on this endpoint (default: $AVN_JUDGE_MODEL)")
    ap.add_argument("--check", action="store_true", help="connectivity only")
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    args = ap.parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    client = A.get_client()
    ok = G.check(client, models)
    if args.check:
        sys.exit(0 if ok else 1)
    if not ok:
        sys.exit("endpoint check failed: fix the key or the model names above before generating")
    out = G.run_generate(client, models, None if args.all else args.per_class, args.seed, args.workers,
                         args.max_tokens, args.out)
    print()
    J.run_judge(client, os.path.join(out, "responses.jsonl"), args.workers, args.judge_model)


if __name__ == "__main__":
    main()
