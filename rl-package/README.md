# Over-refusal RL: build package

This package describes a system that teaches an open model an organization's security policy with reinforcement
learning. Use it to build the system in your own harness. It contains no training code and no dataset text. It gives
the design, the settings, the libraries and versions, the judge prompts, the numbers to expect, and a check for each
part. The `skills/` folder holds two skill files for a coding agent: one for building the system, one for running it.

Where the package gives a value, use it. If you depart from a value, write down why (build skill, "Keep a log").

## What the system does

A security assistant built on a stock open model refuses much legitimate security work (exploit PoCs for authorized
tests, ATT&CK technique code, malware analysis) and still answers some requests it should refuse. Rejection-sampling
RL (also called expert iteration) fixes both at once. Each round:

1. Sample several answers per training prompt from the current model.
2. An LLM judge labels each answer as full compliance, partial refusal or full refusal.
3. Keep the answers that did the right thing for their prompt: comply on legitimate work, refuse real threats.
4. For a prompt where nothing passed, an ISR judge writes a note on what was wrong and the model tries again (ISR,
   iterative self-refinement). A passing revision is kept and trained as if it had been the first answer.
5. Fine-tune a LoRA adapter for one epoch on a draw from the pool of kept answers, publish it to
   the serving engine, and repeat.

## Expected result

On the held-out set of 221 legitimate and 249 harmful requests, with `google/gemma-4-26B-A4B-it`: over-refusal falls
from about 70-73% to about 22-27%, and leak (harmful requests answered) from about 9-11% to about 4-5.5%, in 8 rounds
of about 5-6 minutes each (about 45 minutes). Estimated judge cost: about $1-1.5 per round including the evaluation,
about $10-15 for an 8-round run. Details: `07_RESULTS.md`.

## What you need

- Two GPUs with at least about 80 GB each, one to train and one to serve (for example NVIDIA H100 80 GB, H200, GH200
  or A100 80 GB). Training peaks at about 52-75 GB; the bf16 model takes about 49 GB on the serve plus KV cache. The
  two machines share a filesystem, or copy each adapter (about 25 MB) across.
- The base model `google/gemma-4-26B-A4B-it` (a 26B mixture-of-experts model with about 4B active parameters).
- The dataset: `train_policy.jsonl` (530 prompts), `eval/policy_unblock.jsonl` (221), `eval/policy_block.jsonl`
  (249) and `policy.md`. From the root of this repository, `python data/build_data.py` downloads every source at a
  pinned revision, verifies each row against `data/CHECKSUMS` and writes these files under `data/` (sources and
  licenses: `data/DATA_PROVENANCE.md`).
- An OpenRouter API key for the judge model `deepseek/deepseek-v4.1-flash`. It labels every sample for the reward,
  labels the held-out answers, and writes the ISR notes. Estimate about $1-1.5 per round in judge calls, including the
  evaluation (`07_RESULTS.md` §7.3).
- The skill files: copy `skills/` to where your harness loads skills from (for Claude Code,
  `.claude/skills/` in your own project).

## Handling the data

The data is harmful by design: part of it is requests the model must learn to refuse. Never print prompt text,
`policy.md` or sampled answers anywhere outside the run directory. Work from the schema, counts and ids. Test each
component with benign hand-written rows. Keep the data out of public repositories.

## Reading order

| File | What it covers |
|---|---|
| `01_PROBLEM_AND_METRICS.md` | the task, the data, the three labels, the metrics, held-out evaluation, the judge |
| `02_ARCHITECTURE.md` | components, the two-GPU split, loop schedule, adapter hand-off, round numbering, run layout |
| `03_ALGORITHM.md` | one round: prompt selection, two-phase sampling, reward, ISR, replay pool, draw, batch summary |
| `04_TRAINING.md` | LoRA, rows and loss, optimizer, packing, output-layer memory, trainer, export, adapter check |
| `05_SERVING.md` | vLLM settings, runtime adapter loading, requests, the prefix cache |
| `06_STACK.md` | pinned versions, trainer requirements, orchestration and process hygiene, ARM (aarch64) notes |
| `07_RESULTS.md` | target numbers: stock, the expected curve, batch statistics, time and cost, build checks |
| `skills/build-overrefusal-rl/` | build milestones and their checks |
| `skills/run-overrefusal-rl/` | health checks, changing settings, reading a batch summary, rules to keep |

## How to know your build is right

Work in this order and pass each check before the next. Every number here is in `07_RESULTS.md`.

1. **Stock model.** Served and evaluated on the held-out sets, it gives about 70-73% over-refusal, 9-11% leak and
   macro F1 about 55-58. If you are far from that, check the evaluation and the judge before going on.
2. **One sampling batch from the base.** About 475 prompts (about 169 signal / 81 answered / 225 refuse) and about
   1,900 samples. First-try pass rates (share of the cell's prompts with at least one of the k samples kept, before
   ISR) about 18-24% (signal), 82-88% (answered) and 67-73% (refuse). ISR passes about 35-55% of attempts on `answer`
   prompts and over 90% on `refuse` prompts. Sampling and judge failures under about 2% of prompts. About 4-5.5
   minutes and about $1-1.5.
3. **One training epoch.** Loss only on the answer tokens; about 11 optimizer steps per 700-row epoch (up to about 50k
   tokens each). The adapter loads into the serve by absolute path in seconds and passes the adapter check: per-row
   log-prob deltas (adapter minus base) on trainer and serve have the same sign, and |served − trainer| ≤ 0.35 ×
   max(|served|, |trainer|) on rows with |delta| > 3 nats.
4. **First rounds.** At learning rate 1e-4 with clipping at 1.0: round 1 stays close to stock (over-refusal down by
   0-15 points, leak at or below stock); round 2 gives about 30-60% over-refusal and about 5-11% leak (at most about a
   point above stock). By round 8: about 22-27% over-refusal, 4-5.5% leak and macro F1 about 85. One evaluation with
   one sample per prompt moves by about ±2.5 points on over-refusal and ±1 point on leak; use 2 samples per prompt,
   and compare the trend over several rounds, not single values.
