#!/usr/bin/env bash
# Build the dataset into data/ (kept out of git). The prompts are not ours to redistribute: build_data.py downloads
# each upstream source at a pinned revision and takes the rows named in data/manifest.jsonl - see
# data/DATA_PROVENANCE.md. Kept as a wrapper so older instructions still work.
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/build_data.py" "$@"
