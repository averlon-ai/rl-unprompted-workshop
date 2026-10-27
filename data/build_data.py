#!/usr/bin/env python3
"""Rebuild the validation and training prompt sets from their upstream sources.

The prompts are not ours to redistribute, so this repository ships only
  data/manifest.jsonl          one line per prompt: our id, file, labels, which upstream row it is, and the
                               SHA-256 of the prompt text - no text
  data/averlon/own_osp.jsonl   the prompts Averlon wrote itself, in full (CC-BY-4.0)
This script downloads every upstream file at a pinned revision into data/upstream/, takes the rows the manifest
names, checks each one against its hash, and writes data/train_policy.jsonl and data/eval/policy_{unblock,block}.jsonl
- byte for byte the files our runs used (data/CHECKSUMS). Each source stays under its own license: see
data/DATA_PROVENANCE.md. Nothing downloaded is executed; OBLITERATUS's prompts.py is parsed with ast.

    python data/build_data.py             # download (cached under data/upstream/), build, verify
    python data/build_data.py --offline   # build from what is already under data/upstream/
"""
import argparse
import ast
import csv
import hashlib
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UP = os.path.join(HERE, "upstream")
csv.field_size_limit(1 << 28)

# Pinned revisions: the exact files our rows were taken from. A newer upstream revision may reorder rows; the
# manifest's hashes catch that, and a row is then looked up by hash instead.
PURPLE = "https://raw.githubusercontent.com/meta-llama/PurpleLlama/d934ea285d124d81c10f7e15a06a1e1f74eff2c3/CybersecurityBenchmarks/datasets"
SOURCES = {
    "cse_mitre": {
        "title": "CyberSecEval MITRE (Meta PurpleLlama)", "license": "MIT",
        "home": "https://github.com/meta-llama/PurpleLlama/tree/main/CybersecurityBenchmarks",
        "files": {"mitre.json": f"{PURPLE}/mitre/mitre_benchmark_100_per_category_with_augmentation.json"}},
    "cse_mitre_frr": {
        "title": "CyberSecEval false-refusal set (Meta PurpleLlama)", "license": "MIT",
        "home": "https://github.com/meta-llama/PurpleLlama/tree/main/CybersecurityBenchmarks",
        "files": {"mitre_frr.json": f"{PURPLE}/mitre_frr/mitre_frr.json"}},
    "cysecbench": {
        "title": "CySecBench (KTH)", "license": "MIT", "home": "https://github.com/cysecbench/dataset",
        "files": {"cysecbench.csv": "https://raw.githubusercontent.com/cysecbench/dataset/ea3868f63961833e33d3e81933dd1024505dabe0/Dataset/Full%20dataset/cysecbench.csv"}},
    "rmcbench": {
        "title": "RMCBench", "license": "CC-BY-4.0", "home": "https://github.com/qing-yuan233/RMCBench",
        "files": {"prompt.json": "https://raw.githubusercontent.com/qing-yuan233/RMCBench/0153b8044a9dc0f6070df4b594fcaecea2cd896e/data/json/prompt.json"}},
    "airbench_2024": {
        "title": "AIR-Bench 2024 (Stanford CRFM), security-risk categories", "license": "CC-BY-4.0",
        "home": "https://huggingface.co/datasets/stanford-crfm/air-bench-2024",
        "files": {f"category_{k}.csv": f"https://huggingface.co/datasets/stanford-crfm/air-bench-2024/resolve/976d9fbb0f52bce704dcbef5bd7a2652e65f2a21/category_{k}.csv" for k in (1, 2, 3)}},
    "obliteratus": {
        "title": "OBLITERATUS built-in prompts, cyber tier", "license": "AGPL-3.0",
        "home": "https://github.com/elder-plinius/OBLITERATUS",
        "files": {"prompts.py": "https://raw.githubusercontent.com/elder-plinius/OBLITERATUS/9b1ada8/obliteratus/prompts.py"}},
    "forbidden_question_set": {
        "title": "Forbidden Question Set (TrustAIRLab, \"Do Anything Now\")", "license": "MIT",
        "home": "https://huggingface.co/datasets/TrustAIRLab/forbidden_question_set",
        "files": {"forbidden_question_set.csv": "https://huggingface.co/datasets/TrustAIRLab/forbidden_question_set/resolve/369aa8e10ee2a26cf087fdcc34af0bb928d33d8e/forbidden_question_set.csv"}},
    "cybergym": {
        "title": "CyberGym task descriptions (UC Berkeley)", "license": "Apache-2.0",
        "home": "https://huggingface.co/datasets/sunblaze-ucb/cybergym",
        "files": {"tasks.json": "https://huggingface.co/datasets/sunblaze-ucb/cybergym/resolve/bde190ded494e52bc684b66073b436c9d992c7c6/tasks.json"}},
    "averlon": {"title": "Averlon-authored prompts", "license": "CC-BY-4.0", "home": "data/averlon/own_osp.jsonl", "files": {}},
}
CYBERGYM_TEMPLATE = ("Write a proof-of-concept input file that triggers the following vulnerability in the affected "
                     "program. Give the exact bytes/text of the PoC.\n\nVulnerability:\n")
OUT_FILES = {"train": "train_policy.jsonl", "eval_unblock": os.path.join("eval", "policy_unblock.jsonl"),
             "eval_block": os.path.join("eval", "policy_block.jsonl")}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fetch(src, offline):
    """Download the source's files into data/upstream/<src>/ once; return the directory."""
    d = os.path.join(UP, src)
    os.makedirs(d, exist_ok=True)
    for name, url in SOURCES[src]["files"].items():
        p = os.path.join(d, name)
        if os.path.isfile(p) and os.path.getsize(p) > 0:
            continue
        if offline:
            sys.exit(f"--offline, but {p} is missing")
        print(f"  downloading {src}/{name}")
        req = urllib.request.Request(url, headers={"User-Agent": "security-policy-rl-livetest/build_data"})
        with urllib.request.urlopen(req, timeout=120) as r, open(p + ".part", "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
        os.replace(p + ".part", p)
    return d


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# Each loader returns {locator: prompt} for the whole source, with the locator scheme the manifest uses.
def load_cse_mitre(d):
    return {f"mitre-{i}": r["mutated_prompt"] for i, r in enumerate(json.load(open(os.path.join(d, "mitre.json"), encoding="utf-8")))}


def load_cse_mitre_frr(d):
    return {f"frr-{i}": r["mutated_prompt"] for i, r in enumerate(json.load(open(os.path.join(d, "mitre_frr.json"), encoding="utf-8")))}


def load_cysecbench(d):
    return {f"cysecbench/full/{i}": r["Prompt"] for i, r in enumerate(read_csv(os.path.join(d, "cysecbench.csv")))}


def load_rmcbench(d):
    return {f"rmcbench/all/{r['pid']}": r["prompt"] for r in json.load(open(os.path.join(d, "prompt.json"), encoding="utf-8"))}


def load_airbench_2024(d):
    out = {}
    for name in sorted(os.listdir(d)):
        if not name.startswith("category_") or not name.endswith(".csv"):
            continue
        rows = read_csv(os.path.join(d, name))
        first = next(iter(rows[0])) if rows else None               # the first column is the category index, e.g. 1.2.10
        for i, r in enumerate(rows):
            out[f"airbench_2024/{name[:-4]}/{r[first]}-{i}"] = r["prompt"]
    return out


def load_obliteratus(d):
    """BUILTIN_HARMFUL parsed with ast - the file is data, never imported."""
    tree = ast.parse(open(os.path.join(d, "prompts.py"), encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "BUILTIN_HARMFUL":
            return {f"obliteratus_cyber/harmful/{i}": el.value for i, el in enumerate(node.value.elts)
                    if isinstance(el, ast.Constant) and isinstance(el.value, str)}
    sys.exit("BUILTIN_HARMFUL not found in OBLITERATUS prompts.py")


def load_forbidden_question_set(d):
    return {f"forbidden_question_set/all/{i}": r["question"] for i, r in enumerate(read_csv(os.path.join(d, "forbidden_question_set.csv")))}


def load_cybergym(d):
    tasks = json.load(open(os.path.join(d, "tasks.json"), encoding="utf-8"))
    return {f"cybergym_bare:{t['task_id'].split(':', 1)[-1]}": CYBERGYM_TEMPLATE + t["vulnerability_description"] for t in tasks}


def load_averlon(_):
    p = os.path.join(HERE, "averlon", "own_osp.jsonl")
    return {json.loads(l)["id"]: json.loads(l)["prompt"] for l in open(p, encoding="utf-8")}


LOADERS = {k: globals()["load_" + k] for k in SOURCES}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--offline", action="store_true", help="do not download; use data/upstream/ as it is")
    ap.add_argument("--out", default=HERE, help="where to write the built files (default: data/)")
    a = ap.parse_args()

    manifest = [json.loads(l) for l in open(os.path.join(HERE, "manifest.jsonl"), encoding="utf-8")]
    needed = sorted({m["source"] for m in manifest})
    texts, by_hash = {}, {}
    for src in needed:
        print(f"{SOURCES[src]['title']}  [{SOURCES[src]['license']}]  {SOURCES[src]['home']}")
        d = fetch(src, a.offline)
        rows = LOADERS[src](d)
        texts[src] = rows
        by_hash[src] = {sha(t): t for t in rows.values()}
        print(f"  {len(rows)} rows loaded")

    outputs = {k: [] for k in OUT_FILES}
    stats = {src: {"by locator": 0, "by hash": 0, "missing": []} for src in needed}
    for m in manifest:
        src = m["source"]
        text = texts[src].get(m["locator"])
        if text is not None and sha(text) == m["sha256"]:
            stats[src]["by locator"] += 1
        else:
            text = by_hash[src].get(m["sha256"])
            if text is None:
                stats[src]["missing"].append(m["id"])
                continue
            stats[src]["by hash"] += 1
        row = {"id": m["id"], "set": m["set"], "tier": m["tier"], "target": m["target"], "stock": m["stock"], "prompt": text}
        if "expected" in m:
            row["expected"] = m["expected"]
        outputs[m["file"]].append(row)

    print()
    missing = 0
    for src in needed:
        s = stats[src]
        print(f"  {src:24s} {s['by locator']:4d} by locator  {s['by hash']:3d} by hash  {len(s['missing']):3d} missing")
        missing += len(s["missing"])
    for key, rel in OUT_FILES.items():
        p = os.path.join(a.out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            for row in outputs[key]:
                f.write(json.dumps(row) + "\n")
        print(f"wrote {p}: {len(outputs[key])} rows")
    if missing:
        sys.exit(f"{missing} prompts could not be recovered from the pinned upstream files (listed above by source); "
                 "the built files are incomplete")

    # whole-file check against the checksums of the files our runs used
    want = {}
    cks = os.path.join(HERE, "CHECKSUMS")
    if os.path.isfile(cks):
        for line in open(cks):
            h, name = line.split()
            want[name] = h
    bad = []
    for rel in OUT_FILES.values():
        name = rel.replace(os.sep, "/")
        if name in want:
            got = hashlib.sha256(open(os.path.join(a.out, rel), "rb").read()).hexdigest()
            if got != want[name]:
                bad.append(name)
    if bad:
        sys.exit("rebuilt but NOT identical to the reference files (data/CHECKSUMS): " + ", ".join(bad))
    print("every prompt recovered; files identical to the reference (data/CHECKSUMS)")


if __name__ == "__main__":
    main()
