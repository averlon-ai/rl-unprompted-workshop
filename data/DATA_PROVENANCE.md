# Data provenance and licensing

The prompt sets are **not distributed by this repository**. The prompts come from public benchmarks that stay under
their own licenses, plus prompts Averlon wrote itself. What ships here:

| file | what it is |
|---|---|
| `data/manifest.jsonl` | one line per prompt (1,000): our id, which output file it belongs to, our labels (`tier`, `target`, `stock`, `expected`), the upstream source and row (`locator`), and the SHA-256 of the prompt text. No prompt text. |
| `data/averlon/own_osp.jsonl` | the 211 prompts Averlon authored, in full |
| `data/build_data.py` | downloads each upstream file at a pinned revision, takes the rows the manifest names, checks each against its hash, writes the three files below. Nothing downloaded is executed. |
| `data/CHECKSUMS` | SHA-256 of the three built files and of `policy.md`: a rebuild is known to be exactly the set our runs used, labelled under exactly that policy text |
| `data/policy.md` | the policy the labels follow |

`python data/build_data.py` writes `data/train_policy.jsonl` (530 prompts) and the
held-out `data/eval/policy_unblock.jsonl` (221) and `data/eval/policy_block.jsonl` (249): 1,000 prompts, 500 *refuse* /
500 *comply*. Downloads are cached under `data/upstream/` (gitignored).

**The labels are ours, not the upstream datasets'.** Every prompt was labelled against `data/policy.md` by two
independent LLM judges; `expected` (`comply` / `refuse`) is that label — `target` (`answer` / `refuse`) is the same
label in the spelling the code uses — and `stock` is what the stock model did before training. Upstream labels and categories are not used.

## Sources

Counts are held-out / train. Revisions are the ones pinned in `build_data.py`.

| source | manifest `set` | rows | license | upstream |
|---|---|---|---|---|
| CyberSecEval, Meta PurpleLlama (`CybersecurityBenchmarks`: MITRE and false-refusal sets) | `cse_mitre`, `cse_mitre_frr` | 87 / 127 | MIT (`CybersecurityBenchmarks/LICENSE`) | https://github.com/meta-llama/PurpleLlama |
| CySecBench (KTH) | `pub_cysecbench_s1000`, `cys_*` | 78 / 130 | MIT | https://github.com/cysecbench/dataset |
| RMCBench | `pub_rmcbench` | 23 / 51 | CC-BY-4.0 | https://github.com/qing-yuan233/RMCBench |
| AIR-Bench 2024 (Stanford CRFM), security-risk categories | `pub_airbench_security` | 32 / 23 | CC-BY-4.0 | https://huggingface.co/datasets/stanford-crfm/air-bench-2024 |
| OBLITERATUS built-in prompts, cyber tier | `pub_obliteratus_cyber` | 28 / 30 | AGPL-3.0 | https://github.com/elder-plinius/OBLITERATUS |
| Forbidden Question Set (TrustAIRLab) | `pub_forbidden_malware` | 15 / 12 | MIT | https://huggingface.co/datasets/TrustAIRLab/forbidden_question_set |
| CyberGym task descriptions (UC Berkeley), under a fixed Averlon prompt template | `own_cybergym_bare` | 75 / 78 | Apache-2.0 | https://huggingface.co/datasets/sunblaze-ucb/cybergym |
| Averlon-authored: templated pentest requests around public CVE records | `own_osp_authorized`, `own_osp_threat` | 132 / 79 | CC-BY-4.0 (ours) | `data/averlon/own_osp.jsonl` |

Each source remains under its own license; this repository's Apache-2.0 license covers the code, the manifest and
the Averlon-authored prompts. Prompt text is normalized only as far as the loaders in `build_data.py` show (none of
it is rewritten), and the hashes in the manifest are of the exact text our runs used.
