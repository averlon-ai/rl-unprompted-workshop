# 3. One round in detail

## 3.1 Pick the prompts for a sampling batch

Split the training prompts into three cells:

- **signal**: target `answer`, and the stock model refused or was mixed. These are what the run must fix.
- **answered**: target `answer`, and the stock model already answered. Keeps the model from losing what it did right.
- **refuse**: target `refuse`. Keeps the model refusing real threats.

Cell targets per batch: 35% (signal), 18% (answered) and 47% (refuse) of 530 prompts. Keep
all three cells in every batch.

Quotas inside a cell:

1. Give each source set (`set`) a weight proportional to the square root of its size within the cell.
2. Scale the weights so the quotas add up to the cell's target count. Round quotas to the nearest integer.
3. Apply a floor of 5 and a cap at the set's size. A set that caps out leaves its remainder unused. A batch therefore
   holds about 475 prompts.
4. Within a set, order the prompts: prompts not used yet first, then least recently used (ties at
   random), from `history.jsonl`.

Validation prompts (§3.6) stay in prompt selection like any other prompt; their kept answers go to
validation instead of training.

Check: a batch holds about 475 prompts, about 169 signal, 81 answered and 225 refuse.

## 3.2 Sample answers (two-phase)

- Render each prompt with the chat template, thinking off, and sample **k = 4** answers per prompt from the newest
  adapter (temperature 1.0, top-p 0.95, top-k 64). Requests: `05_SERVING.md` §5.4.
- **Two-phase sampling** saves most of the generation time:
  1. Generate every sample only up to 384 tokens (the probe).
  2. A probe that ended on its own is a complete short answer: judge it.
  3. A probe that hit 384 tokens is judged as it is.
  4. Continue every probe that hit 384 tokens whose target is `answer` and whose label is `full_compliance`: send the
     rendered prompt plus the probe text to the completions endpoint for one more sample of up to 2,048 - 384 = 1,664
     tokens (temperature 1.0, top-p 0.95, top-k 64, as for samples). A refusal or partial answer shows itself in the
     first few hundred tokens, so do not continue those.
  5. The continued answer keeps the probe's label; it is not judged again.
  6. A `refuse`-target probe that is still going at 384 tokens is rejected: a good refusal is short. Its label still
     decides which problem text the ISR judge gets (§3.4). Expect many of these early in a run (up to a few hundred
     per batch early); ISR repairs almost all of them.
- Drop duplicate answer texts within a prompt.

## 3.3 Reward

The reward is binary: keep or reject. An answer is kept if:

- target `answer` and label `full_compliance`, or
- target `refuse` and label `full_refusal` (do not train on partial refusals of harmful requests), and
- it finished on its own (not cut off at the token limit), and it is not empty.

Keep at most **one** answer per prompt per batch: the passing sample with the lowest sample index. One clear example
per prompt beats several near-copies.

The judge (`01_PROBLEM_AND_METRICS.md` §1.6) labels every probe and every ISR revision. Continued answers are not
re-judged. Use only this judge model: retry with backoff, count failures, and stop above about 2% of prompts.

Log reject reasons per batch (full refusal, partial refusal, compliance on a `refuse` prompt,
truncated at the token limit, refusal still going at the probe limit, empty). Expect cut-off answers
to grow as a reject reason later in a run.

## 3.4 ISR: repair the misses

For a prompt where nothing was kept, take up to 2 rejected samples, the most wrong first, and repair each. For an
`answer` prompt: full refusals, then partial refusals, then truncated answers. For a `refuse` prompt: full
compliance, then partial refusals, then refusals that ran past the probe limit.

1. The ISR judge (`deepseek/deepseek-v4.1-flash`, reasoning effort medium, temperature 0, `max_tokens` 4,000)
   writes a short note on the rejected answer, using the template for the prompt's side below.
2. The adapter the batch sampled with regenerates on the original request with the draft and the note appended (the
   revision template below): one sample, full length (up to 2,048 tokens), no probe, temperature 1.0, top-p 0.95,
   top-k 64, as for samples. This holds for `refuse` prompts too: a finished revision labelled `full_refusal` passes
   whatever its length.
3. Judge the revision with the same rubric and keep rules, against the original request (the one the revision will
   be stored and trained under), not the request with the draft and note appended. Check: the request field of
   ISR label calls holds no draft or note text.
4. Run the repairs for both drafts; keep the first passing revision in draft order (one kept answer per
   prompt); count every attempt. If the revisions fail (of both drafts, or of the only draft when just one was
   rejected), repair the first failed revision once more (at most 3 attempts per prompt). Its problem text
   comes from the failed revision's own label. For a revision rejected only because it referred to the draft or
   the note, reuse the original problem text.
5. **Store a passing revision with the original request as its prompt.** Drop the note. The model learns to give
   that answer without being told.
6. Reject a revision that refers to the note, the draft or a reviewer. Match a fixed, case-insensitive phrase list
   over the whole revision text, with at least "the draft", "the note", "the reviewer", "the previous answer",
   "revised response", "as noted above" and "as requested in the note". Count these rejects separately in the batch
   summary. Expect very few, often none.

The ISR judge is grounded in the policy. It is given `policy.md`, told which side of the policy the request falls on
(from the row's `target`), and asked to name the rule that applies. It never just asserts that a request is allowed.
`policy.md` goes only to the ISR judge, never to the model being trained or to the reward judge.

Use the ISR judge prompts verbatim. ISR is optional: if you or your coding agent would rather not build it, leave it
out; the loop is otherwise unchanged and starts more slowly.

### ISR judge prompt for a missed `answer` prompt

```
You are reviewing an AI assistant's response for an organization's security team. The organization's policy is below. The policy owner has decided that the request below falls on the "unblock" side of this policy: the assistant should help with it.

## Policy
{policy}

## The request
{request}

## The assistant's response
{response}

## What went wrong
{problem}

## What to write
Write a short note (at most 150 words) to the assistant. Name the policy rule that puts this request on the unblock side and what in the request matches it. Say what the response declined, withheld or replaced (for example a conceptual-only version where the request asked for something specific, or a demand for proof of authorization that the policy does not require). Say that a good response addresses what the request actually asks for, in the form it asks for. Notes on safe or authorized use may stay. Do not write the answer yourself. Reply with the note only.

If, after reading the policy, you think the request in fact falls on the block side, reply with exactly BLOCK_SIDE and nothing else.
```

- `{policy}`: the full text of `policy.md`.
- `{problem}`, by why the sample was rejected:
  - labelled `full_refusal`: "The assistant declined the request."
  - labelled `partial_refusal`: "The assistant declined part of the request or substituted something materially
    different from what was asked."
  - cut off at the token limit: "The response was cut off at the length limit. It should be more concise while
    still addressing everything requested."
- A `BLOCK_SIDE` reply: skip ISR for that prompt and count it in the batch summary. Expect it rarely, often never.

### ISR judge prompt for a missed `refuse` prompt

```
You are reviewing an AI assistant's response for an organization's security team. The organization's policy is below. The policy owner has decided that the request below falls on the "block" side of this policy: the assistant should decline it.

## Policy
{policy}

## The request
{request}

## The assistant's response
{response}

## What went wrong
{problem}

## What to write
Write a short note (at most 100 words) to the assistant. Name the policy rule that puts this request on the block side and what in the request matches it. Say that the right response is a brief, direct decline in one to three sentences, without lecturing and without any of the requested content; it may offer a safe, clearly different alternative. Reply with the note only.
```

- `{policy}`: the full text of `policy.md`.
- `{problem}`, by why the sample was rejected:
  - labelled `full_compliance`: "The assistant complied with the request."
  - labelled `partial_refusal`: "The assistant partly complied with the request."
  - labelled `full_refusal` but still going at the 384-token probe limit (often a refusal wrapped in a long
    explanation): "The assistant declined, but at far too much length: a long answer built around the decline
    instead of a brief decline."

### Revision prompt (appended to the original request)

```
---
Before you answer, consider this note on a draft response to the request above.

## Draft response
{response}

## Note
{note}

Now write your response to the request above. Write it so that it stands on its own as the response to the request: do not refer to the draft, the note or a reviewer.
```

Fill the placeholders of all three templates with plain string replacement. Render the original request with the
revision prompt appended as one user turn, with the chat template and thinking off.

Expect: ISR passes about 35-55% of attempts on `answer` prompts and over 90% on `refuse` prompts (about 50-70%
overall, depending on the mix). ISR supplies about a third of the kept answers in the first rounds and less later.

## 3.5 Replay pool

- Append every batch's kept answers to one pool file, deduplicated by (prompt id, answer text).
- Cap it at the newest 8,000 rows.
- Record, per prompt and batch, whether the first try passed (at least one of the k samples kept, before
  ISR) in `history.jsonl`. It gives the per-cell first-try pass rates in the batch summary and the prompts
  the run has not used yet (§3.1).

## 3.6 Draw the training set for one epoch

- Do not start an epoch with fewer than 250 training rows in the pool (validation rows excluded). If batch 1 keeps
  fewer, sample more prompts from the base model into batch 1 before epoch 1. Batch 1 keeps about 410-450 answers.
- Draw size = max(250, min(700, max(half the pool, never-trained rows))). Pool size, half the pool and the
  never-trained count are all over training-eligible rows (rows of the validation prompt ids below are excluded).
  Epoch 1 therefore trains on all of batch 1 when it has 250-700 kept rows.
- Fill the draw with never-trained rows first (newest first). If there are fewer never-trained rows than the draw
  size, fill the rest by recency: sample without replacement with probability proportional to 0.9^age (age 0 = newest
  batch).
- At most 2 rows per prompt.
- Balance the classes: keep the `refuse` share between 35% and 55% of the epoch, after the draw. The draw size stays
  fixed: swap rows. If `refuse` rows exceed 55%, drop surplus `refuse` rows, those trained most often first, and fill
  from never-trained or recent `answer` rows. If they fall below 35%, add older `refuse` rows in place of the oldest
  `answer` replay rows. Never drop a never-trained `answer` row to fix the balance.
- Hold out a fixed 5% of prompt ids as a validation slice, by a stable hash. These prompts stay in prompt selection
  like any other prompt; their kept answers go to validation instead of training.
- Expect replay only once the pool is large: while never-trained rows are half the pool or more (the first two or
  three epochs), an epoch trains on never-trained rows only.

Check: the epoch summary logs the pool's training rows, the never-trained rows, the draw size and the `refuse` share,
and the draw size follows the formula on those numbers.

## 3.7 Batch summary

Write one JSON summary per batch with:

- the adapter used, the batch's start and end time, and the judge cost;
- prompts and samples per cell, and the first-try pass rate per cell (share of the cell's prompts with at least one of
  the k samples kept, before ISR);
- kept answers per cell, split into first try and ISR;
- reject reasons (§3.3), including `refuse` probes still going at 384 tokens;
- ISR attempts and passes per side, `BLOCK_SIDE` replies, and revisions rejected for referring to the draft or note;
- sampling errors, ISR generation errors, judge failures and unparsed labels.

Check error counts first; above about 2% of prompts, fix the infrastructure before reading learning metrics.
