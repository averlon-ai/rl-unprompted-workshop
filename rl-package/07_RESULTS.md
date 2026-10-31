# 7. Targets

All numbers are held-out over-refusal / leak in %, labelled by `deepseek/deepseek-v4.1-flash` with the rubric in
`01_PROBLEM_AND_METRICS.md` §1.6, at learning rate 1e-4 with gradient clipping at 1.0.

## 7.1 The expected curve

1 eval sample per prompt, n = 470:

| Round | Over-refusal | Leak |
|---|---|---|
| 0 (stock) | about 70-73 | 9-11 (macro F1 about 55-58) |
| 1 | close to stock (down by 0-15 points) | at or below stock |
| 2 | about 30-60 | about 5-11 (at most about a point above stock) |
| 4 | about 30-45 | 5-8 |
| 6 | about 28-38 | 4-7 |
| 8 | about 22-27 | 4-5.5 (macro F1 about 85) |

These targets assume the settings and the schedule in this package (`02_ARCHITECTURE.md` §2.3).

- Compare the trend over several rounds, not single values.
- Eval noise: about ±2.5 points over-refusal and ±1 point leak per round with one sample per prompt. Use 2 samples per
  prompt or compare several rounds before concluding.

## 7.2 One sampling batch

First-try pass rate: the share of the cell's prompts with at least one of the k samples kept, before ISR
(`03_ALGORITHM.md` §3.7).

| Quantity | Target |
|---|---|
| prompts | about 475 (about 169 signal / 81 answered / 225 refuse) |
| samples | about 1,900 |
| judge calls | about 1,900 sample labels, plus up to about 400 ISR notes and as many revision labels |
| first-try pass rate, first batch | signal about 18-24%, answered about 82-88%, refuse about 67-73% |
| first-try pass rate, later batches | rises for `signal` prompts round by round; the other cells stay roughly flat |
| ISR pass rate | about 35-55% on `answer` prompts, over 90% on `refuse` prompts (about 50-70% overall) |
| ISR share of kept answers | about a third early, less later |
| `BLOCK_SIDE` replies | rare, often none |
| revisions rejected for referring to the draft or note | very few, often none |
| `refuse` probes still going at 384 tokens | up to a few hundred per batch early |
| sampling and judge failures | under about 2% of prompts |
| kept answers | about 410-450 per batch early (about 225 `refuse`, the rest `answer`), about a third from ISR |
| time | about 4-5.5 min |
| judge cost (estimate) | about $1-1.5 |

## 7.3 Time and cost to budget

Timings assume one 80-96 GB-class GPU per role; slower GPUs take proportionally longer.

| Step | Time | Judge cost (estimate) |
|---|---|---|
| sampling batch | about 4-5.5 min | about $1-1.5 |
| training epoch (persistent trainer) | about 2.5-4.5 min | none |
| held-out eval, 1 sample per prompt | about 1.5-2.5 min | about $0.2 |
| held-out eval, 2 samples per prompt | about 2-4.5 min | about $0.3-0.4 |
| round (loops in parallel) | about 5-6 min | about $1-1.5 including the evaluation |
| 8-round run | about 45 min | about $10-15 including the evaluations |

## 7.4 Build checks

| Check | Target |
|---|---|
| LoRA | 115 adapted modules, about 11.49M trainable parameters |
| optimizer steps | about 11 per 700-row epoch (up to about 50k real tokens per step) |
| step time | about 20 s |
| peak trainer memory | about 52 GB after loading, up to about 75 GB with 8-16k-token micro-batches |
| loss vs transformers' own loss | within about 0.1%; without the softcap the loss comes out about twice as high |
| chunked vs unchunked loss | equal |
| validation loss | lower after the epoch than before on the same rows in early epochs; a small rise later is normal |
| adapter check, pass | same sign; \|served − trainer\| ≤ 0.35 × max(\|served\|, \|trainer\|) if \|delta\| > 3 nats |
| adapter check, fail | a served delta near 0 |
