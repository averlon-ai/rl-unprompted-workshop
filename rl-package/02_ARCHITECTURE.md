# 2. Architecture

## 2.1 Components

- **Serving engine** (serve GPU): hosts the base model plus LoRA adapters and loads each new adapter at runtime;
  answers all sampling, ISR revisions and held-out generation.
- **Sampler** (CPU process, talks to the serve over HTTP): picks prompts, samples answers from the newest adapter,
  calls the judge, runs ISR, appends kept answers to the replay pool.
- **Trainer** (train GPU): one persistent process; draws from the replay pool, builds the training rows, trains one
  LoRA epoch, exports the adapter, publishes it.
- **Evaluator** (CPU process, talks to the serve over HTTP): for each new adapter, generates on the held-out sets,
  judges, writes the round's metrics.
- **Watchdog** (CPU process): keeps the loops and the serve running (restarts any that exit).
- **Judge API** (remote, OpenRouter): the reward judge, the ISR judge and the evaluation judge.

Keep the sampler, trainer and evaluator as separate programs that share one run directory and one control file.

## 2.2 Two GPUs, one shared filesystem

```
               train GPU                                        serve GPU
 ┌───────────────────────────────────┐            ┌───────────────────────────────────┐
 │ trainer: draw -> build -> 1 epoch │  adapter   │ vLLM: base model + LoRA slots     │
 │          -> export -> publish ────┼──(shared ──▶ load_lora_adapter(name, path)     │
 │                                   │   disk)    │ sampling, ISR revisions, held-out │
 └───────────────────────────────────┘            └─────────────────▲─────────────────┘
                                                                    │ HTTP /v1/...
 ┌──────────────────────────────────────────────────────────────────┴─────────────────┐
 │ CPU loops, on either machine: sampler, evaluator, watchdog                         │
 └──────────────┬─────────────────────────────────────────────────────────────────────┘
                │ judge calls (reward labels, ISR notes, eval labels)
                ▼
          OpenRouter API
```

The trainer writes an adapter directory on the shared filesystem and the serve loads it by absolute path. If your
machines do not share a disk, copy the adapter (about 25 MB) to the serve machine before loading it. The CPU loops
(sampler, evaluator, watchdog) can run on either machine.

## 2.3 Loop scheduling

A sampling batch takes about 4-5.5 minutes and a training epoch about 2.5-4.5 minutes. The sampler and the trainer run
as independent loops, on this schedule:

- **Round 1 runs strictly in sequence.** Epoch 1 waits for batch 1 (sampled from the base model). Batch 2 waits for
  adapter `r1` and samples with it.
- **Round 2.** Epoch 2 waits for batch 2.
- **From round 3 on, the loops are fully asynchronous.** The trainer starts the next epoch as soon as the previous one
  is published, on whatever the pool holds (`03_ALGORITHM.md` §3.6). Some epochs then have no never-trained rows; that
  is expected. The sampler starts the next batch as soon as one finishes, always on the newest adapter.
- **End of run.** Once the final adapter is published, stop the sampler (abort or discard any batch still in flight).
- The evaluator evaluates each adapter as it is published.

Check: batches 1 and 2 record the base model and `r1`; each epoch logs its never-trained row count; no batch starts
after the final adapter is published.

Build and test the loop in sequence first (sample, train, evaluate, repeat), then switch to this schedule. With
separate programs, only the scheduling changes.

## 2.4 Handing over an adapter

1. The trainer finishes an epoch and exports the next adapter (`rN`) in the serving engine's LoRA format
   (`04_TRAINING.md` §4.8).
2. It writes the adapter's name and **absolute** path to a small "latest adapter" file, atomically (write a temporary
   file, then rename it). Always use absolute paths on the shared filesystem.
3. The sampler and evaluator read that file. Before using an adapter they ask the serve to load it if it is not
   registered yet ("ensure", never "replace").
4. Unload only adapters well behind the newest one: keep the newest 8 registered (`05_SERVING.md` §5.3), so every loop
   keeps the adapter it is using.

Check: from the serve machine, load the newest adapter by the path written in the "latest adapter" file.

## 2.5 Round numbering

Round 0 is the base model. Adapter `rN` is the result of N training epochs: `r1` is trained from the base on batch 1.
Round N's metrics are the held-out evaluation of `rN`. Use this numbering in every log, summary and chart.

## 2.6 Control file

Keep the run's settings (sampling, reward, ISR, training) in a JSON control file that the loops re-read at
every batch and epoch. Write it atomically. Log every change to a decision log with the time, the round, the
old and new value and the reason.

## 2.7 Run layout

```
runs/<name>/
  control.json            settings, re-read every batch/epoch
  decisions.jsonl         every change to control.json
  batches/<batch id>/     tasks, samples, judge labels, kept answers, summary.json
  pool/accepted.jsonl     replay pool
  history.jsonl           per prompt and batch: first-try pass or fail
  train/epoch_<E>/        trainer checkpoint, E counted from 1 (epoch E produces adapter rE)
  adapters/r<N>/          exported adapter for the serve
  latest_adapter          name and absolute path of the newest adapter
  eval/r<N>/              held-out generations and labels
  eval/metrics.jsonl      one line per round: over-refusal, leak, n, P/R/F1
  logs/
```

`history.jsonl` gives the per-cell first-try pass rates in the batch summaries and tells prompt selection which
prompts the run has not used yet (`03_ALGORITHM.md` §3.1).
