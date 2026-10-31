---
name: build-overrefusal-rl
description: >-
  Build a rejection-sampling RL pipeline that teaches an LLM a security policy (comply on legitimate security work,
  refuse real threats) — serving with runtime LoRA loading, two-phase sampling, LLM-judge reward, ISR repair, replay
  pool, one-epoch LoRA training per round, held-out evaluation. Use when starting the build, choosing a component's
  design, or checking that a component behaves as intended.
---

# Build the over-refusal RL pipeline

The design lives in the package next to this skill (`README.md`, `01_...` to `07_...`). Read `README.md` and
`02_ARCHITECTURE.md` before writing any code, and the matching file before each milestone. When the package gives a
number, use it; when you depart from it, record why in the log.

## Principles

- Build in the milestone order below. Do not start a milestone until the previous one passes its check. Check the
  infrastructure counters before drawing conclusions about learning.
- Separate programs for the serve, the sampler, the trainer and the evaluator, sharing one run
  directory and one control file. While building, run the programs in sequence; the run itself uses the
  schedule in `02_ARCHITECTURE.md` §2.3.
- Every program writes a JSON summary per batch / epoch / eval with counts of errors and reject reasons.
- Never print or log API keys. Read them from the environment.
- The dataset contains harmful requests by design. Work from its schema, counts and ids: never print prompt text,
  `policy.md` or sampled answers anywhere outside the run directory. No step of the pipeline requires reading them;
  only the ISR judge receives the policy, at run time. Test with hand-written benign rows, and check the real data
  with counts and labels only.
- Use the ISR judge prompts in `03_ALGORITHM.md` §3.4 verbatim. ISR is optional; without it the loop starts more
  slowly and nothing else changes.

## Milestones and their checks

1. **Environments** (`06_STACK.md` §6.1). Serve env (vLLM) and train env (torch + transformers), separate. Check:
   both import; the train env loads the model config and tokenizer; one prompt rendered with thinking off ends with
   `<|channel>thought\n<channel|>` (`04_TRAINING.md` §4.2).
2. **Serve** (`05_SERVING.md` §5.1-5.2). vLLM on the serve GPU with LoRA enabled. Check: `GET /v1/models` answers;
   one completions request on a rendered benign prompt returns an answer and no thought text; the prompt token ids
   start with exactly one `<bos>` (§5.4).
3. **Judge client** (`01_PROBLEM_AND_METRICS.md` §1.6). OpenRouter client with the rubric, the call settings,
   retries with backoff and cost counting. Check: a hand-written obvious refusal and an obvious compliance get the
   right labels; parse failures and judge failures are counted.
4. **Held-out evaluation of the base, round 0** (`01_PROBLEM_AND_METRICS.md` §1.4-1.5). Generate on both held-out
   sets, judge, compute over-refusal, leak, n and per-class P/R/F1. Check: about 70-73% over-refusal, 9-11% leak,
   macro F1 about 55-58 (`07_RESULTS.md` §7.1). If far off, fix the evaluation before going further.
5. **Sampler, one batch from the base** (`03_ALGORITHM.md` §3.1-3.5, §3.7). Prompt selection by cells, k = 4 two-phase
   sampling, reward, keep rules, ISR, pool append, `history.jsonl`. Check the batch summary against `07_RESULTS.md`
   §7.2: about 475 prompts split about 169 / 81 / 225 (§3.1); about 1,900 samples; first-try pass rates (share of the
   cell's prompts with at least one of the k samples kept, before ISR; §3.7) about 18-24% / 82-88% / 67-73%; ISR pass
   rate about 35-55% on `answer` and over 90% on `refuse` prompts; ISR label calls carry no draft or note text in the
   request field (§3.4); sampling and judge failures under about 2% of prompts; reject reasons broken down (§3.3).
6. **Trainer, one epoch** (`04_TRAINING.md`). Draw from the pool (`03_ALGORITHM.md` §3.6), build rows, train one
   epoch, export a PEFT adapter. Checks:
   - the loss mask covers exactly the answer and closing tokens of a sample row (§4.2);
   - 115 adapted modules, about 11.49M trainable parameters (§4.1);
   - peak memory about 52 GB after loading, up to about 75 GB with 8-16k-token micro-batches; chunked loss equals
     unchunked loss; your loss matches the transformers model's own loss within about 0.1% (§4.5);
   - about 11 optimizer steps per 700-row epoch (§4.4); pre-clip gradient norms logged;
   - validation loss lower after the epoch than before on the same rows (§4.7);
   - the adapter, given by absolute path, loads into the serve and passes the adapter check (§4.8-4.9).
7. **Round loop** (`02_ARCHITECTURE.md` §2.3-2.5, `04_TRAINING.md` §4.6). Publish the adapter as newest, sample the
   next batch with it, train again from the saved adapter and optimizer state, evaluate each adapter. Check: round
   numbers consistent across logs; the second epoch resumes (optimizer state restored, step count continues);
   metrics appended per round and following `07_RESULTS.md` §7.1.
8. **Asynchronous loops and watchdog** (`02_ARCHITECTURE.md` §2.3-2.4, `06_STACK.md` §6.4), only after the sequential
   loop works. Round 1 strictly in sequence; epoch 2 waits for batch 2; from round 3 on, fully asynchronous loops; the
   sampler stops once the final adapter is published. "Latest adapter" hand-off; ensure-only loading; newest 8
   adapters registered; PID files and lock files. Check: batches 1 and 2 record the base and `r1`; each epoch logs its
   never-trained row count; no batch starts after the final adapter.

## Keep a log

Keep one log file for the build and the run:

- each departure from the package's values, and why;
- each milestone check with its result;
- per-round metrics (over-refusal, leak, n, macro F1) next to the targets in `07_RESULTS.md`.
