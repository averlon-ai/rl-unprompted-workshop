---
name: run-overrefusal-rl
description: >-
  Operate and check the health of a running over-refusal rejection-sampling RL run — read batch, epoch and
  eval summaries, tell infrastructure failures from learning problems, decide whether to change a setting,
  and log every change. Use for any "how is training going", any change to the run's control file, and
  whenever a metric looks wrong.
---

# Run and check the over-refusal RL run

Background: package files `03_ALGORITHM.md` (what a batch does), `07_RESULTS.md` (targets).

## Health check, in this order

Stop at the first problem you find and fix it before looking further.

1. **Processes.** Serve answering? Sampler, trainer, evaluator alive (or finished on purpose), each matching its PID
   file? Newest adapter registered on the serve?
2. **Infrastructure errors** in the latest batch summaries: sampling errors, ISR generation errors, judge failures,
   unparsed labels. Above about 2% of prompts, fix the infrastructure before reading any metric.
3. **Judge spend.** Spend so far against the estimate in `07_RESULTS.md` §7.3.
4. **Held-out n.** Each eval labels about all 221 + 249 prompts (times samples per prompt). A smaller n means
   generation or judge failures.
5. **Leak.** If the mean leak of the last 3 rounds rises more than about 2 points above its lowest value so
   far, the refuse side is losing: check the `refuse` share of recent training epochs (35-55%) and the
   refuse cell's first-try pass rate.
6. **Over-refusal.** Compare with `07_RESULTS.md` §7.1; compare the trend over several rounds, not single values
   (about ±2.5 points noise per round with one sample per prompt).

## Changing a setting

- For a short run, do not change settings mid-run.
- In a longer run, change one setting at a time and wait at least 5 batches before judging its effect.
- Write the change to the control file atomically, then append
  `{time, round, setting, old, new, reason}` to the decision log.
- To change a script a loop is running, write a new file and move it into place.
- Stop processes by the PID in their PID file only.

## Reading a batch summary

Targets (`07_RESULTS.md` §7.2), for about 475 prompts at k = 4:

- about 1,900 samples; about 169 / 81 / 225 prompts across signal / answered / refuse;
- first-try pass rates (share of the cell's prompts with at least one of the k samples kept, before ISR) in the first
  batch about 18-24% (signal), 82-88% (answered), 67-73% (refuse); they rise for `signal` prompts round by round, and
  the other cells stay roughly flat;
- ISR: about 35-55% of attempts pass on `answer` prompts, over 90% on `refuse` prompts (about 50-70% overall); ISR
  supplies about a third of kept answers early, less later;
- `BLOCK_SIDE` replies rare, often none; revisions rejected for referring to the draft or note very few, often none;
- `refuse` probes still going at 384 tokens: up to a few hundred per batch early;
- about 4-5.5 minutes and about $1-1.5 (estimate);
- sampling and judge failures under about 2% of prompts.

## Rules to keep

- **Read infrastructure error counts before any learning metric.** Count sampling errors, ISR generation errors and
  judge failures in every batch summary (`03_ALGORITHM.md` §3.7).
- **Log reject reasons per batch**, including answers cut off at 2,048 tokens, which grow as a reject reason later in
  a run (`03_ALGORITHM.md` §3.3).
- **Never unload an adapter another loop may be using.** Load with "ensure" and keep the newest 8 registered
  (`05_SERVING.md` §5.3, `02_ARCHITECTURE.md` §2.4).
- **Thinking off everywhere the model generates**: sampling, probe continuation, ISR revisions, evaluation
  (`03_ALGORITHM.md` §3.2, `05_SERVING.md` §5.4). The judge's reasoning effort is a separate setting.
- **Round numbers.** Adapter `rN` is the result of N epochs; use that in every log and
  chart (`02_ARCHITECTURE.md` §2.5).
- **The answer marker `<channel|>` must appear exactly once** in each training row; skip and count the others
  (`04_TRAINING.md` §4.2).
- **Tokenizer.** Load the tokenizer once in the main thread before starting worker threads (`06_STACK.md` §6.4).
- **Prefix cache.** Give each adapter a name unique across runs; reset the prefix cache before loading new weights
  under an existing name (`05_SERVING.md` §5.5).
