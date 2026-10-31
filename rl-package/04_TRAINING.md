# 4. Training

Each round trains one epoch of supervised fine-tuning on the kept answers, continuing the same LoRA adapter. The RL
signal is entirely in which answers were kept; the training step itself is plain next-token cross-entropy.

## 4.1 Model and LoRA

- Base: `google/gemma-4-26B-A4B-it`, loaded in bf16 (about 49 GB). It is a multimodal wrapper: train only the
  language model and leave the vision and audio towers untouched.
- LoRA on the attention projections only: `q_proj`, `k_proj`, `v_proj`, `o_proj` of every language-model layer. No
  MLP, no experts, no embeddings, no output head.
  - Rank 16, alpha 32 (scale 2), dropout 0.05 on the input during training only.
  - Forward: base output + (alpha / r) · B · A · x.
  - Init: A random (Kaiming uniform), B zero, so the adapter starts as an exact no-op.
  - Only A and B are trainable; every base weight is frozen.
- Select the projections by their path under the language model (`…language_model.layers.*.self_attn.{q,k,v,o}_proj`),
  not by name: the vision tower has modules with the same names. Attach to the linear layer inside any wrapper. A
  small LoRA module of your own is enough; PEFT is not needed.
- Check: 115 adapted modules and about 11.49M trainable parameters (5 of the 30 layers use full attention with shared
  keys and values and have no `v_proj`).

## 4.2 Training rows and the loss

- Each row is the chat-template generation prompt (thinking off) + the kept answer + `<turn|>\n<eos>`. Build rows from
  the generation prompt plus the answer, not from a rendered assistant turn: the template omits the thought channel
  for model turns, so the marker would be absent.
- With thinking off, Gemma 4's generation prompt ends with an empty thought channel closed by `<channel|>`:
  `<bos><|turn>user\n{request}<turn|>\n<|turn>model\n<|channel>thought\n<channel|>`. Everything after the last
  `<channel|>` is the user-visible answer.
- Compute cross-entropy only on the tokens after that marker: the answer and the closing tokens. `<turn|>` (the token
  generation stops on) must be supervised, so the model learns to stop. Prompt tokens get weight 0.
- The marker must appear exactly once. Skip and count any row where it is missing or appears more than once.
- Maximum sequence length 8,192; cut longer rows from the left (prompt side), then run the marker check above. Skip a
  row whose answer alone exceeds the limit.
- Loss = mean over all supervised tokens in the optimizer step (token mean), not a mean per sequence.
- Apply Gemma 4's final logit softcapping, logits = 30 · tanh(raw logits / 30), then
  compute log-softmax in fp32 (§4.5).
- Check: on a sample row, the loss mask covers exactly the answer tokens and the closing tokens.

## 4.3 Optimizer and learning rate

- AdamW, betas (0.9, 0.99), weight decay 0.
- Learning rate 1e-4, gradient-norm clipping at 1.0.
- Schedule: linear warm-up at the very start of the run (learning rate × s/3 for steps s = 1, 2, 3), then constant.
  Do not restart warm-up each round.
- Precision: base weights and activations in bf16; LoRA A/B weights and AdamW state in fp32.
- Activation checkpointing on.
- Treat the whole run as one training job: the adapter, the AdamW moments and the step count carry
  over from round to round (§4.6).

## 4.4 Batching and step count

- One epoch is 250-700 rows (about 500k tokens at 700 rows).
- Sort rows by length, then fill each optimizer step with rows until adding the next row would exceed about 50k tokens
  (count real tokens, not padding). Shuffle the order of the steps. Split each step into micro-batches of 8-16k tokens
  and accumulate gradients. This gives about 11 optimizer steps per 700-row epoch (7 for about 400 rows). Keep this
  packing: the targets in `07_RESULTS.md` assume it.
- Expect about 20 s per optimizer step. Log step time and GPU utilization; the train GPU
  should be busy for most of an epoch.
- Expect pre-clip gradient norms of about 0.1-3, sometimes higher on the step that holds most of the short `refuse`
  rows; clipping at 1.0 covers it.

## 4.5 Output-layer memory

The vocabulary has 262,144 tokens. Full fp32 logits for a 50k-token step would take about 52 GB,
so do both of the following:

1. **Project only the answer positions.** Get the final hidden states from the language model without its output
   head (in transformers 5.13 the model loads as `AutoModelForImageTextToText`; its inner language model returns
   them). Gather the hidden states at the supervised positions and project only those with the model's output head.
   The head is tied to the input embedding (`tie_word_embeddings: true`). Apply the final logit softcapping
   (`final_logit_softcapping: 30` in the config): logits = 30 · tanh(raw / 30), then log-softmax in fp32. Without the
   softcap, the loss is computed against a different distribution from the one the model samples from.
2. **Chunk.** Compute the projection and the loss in chunks of positions (a few thousand at a time) and sum, so the
   full logits tensor never exists at once; keep the loss a token mean over the whole optimizer step. Run
   micro-batches of 8-16k tokens with gradient accumulation to about 50k tokens per optimizer step (§4.4).

Use `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` in the trainer.

Checks:

- Peak GPU memory about 52 GB after loading, up to about 75 GB with 8-16k-token micro-batches.
- Your loss matches the transformers model's own loss (pass `labels` with the prompt positions masked) on a few rows
  to within about 0.1%. Transformers applies the softcap in bf16, so an exact fp32 version differs slightly. Without
  the softcap the loss comes out about twice as high, so this check catches it.
- The chunked loss equals the unchunked loss on a small batch that fits both ways. Compare losses, not gradients (the
  bf16 MoE backward is not bitwise reproducible).

## 4.6 Trainer process and checkpoints

- Run the trainer as one persistent process that keeps the base model in memory. Loading the base takes about
  1.5 minutes; do it once, not every round.
- Save the AdamW state and the step count with every checkpoint, so training can resume exactly.
- Check: the second epoch resumes from the saved adapter and optimizer state, and the step count continues.

## 4.7 Per-epoch routine and logs

1. Draw the epoch's rows from the pool (`03_ALGORITHM.md` §3.6).
2. Before training, score this epoch's validation rows: all validation rows in the pool (kept answers
   of the held-out 5% prompt ids).
3. Train one epoch, continuing the adapter and optimizer state.
4. Log per step: loss, gradient norm before clipping, learning rate, tokens, step time. Log peak GPU memory.
5. After training, score the same rows again, and log both validation losses.
6. Save the checkpoint (adapter, optimizer state, step count).
7. Export the adapter (§4.8) and publish it as the newest adapter (`02_ARCHITECTURE.md` §2.4).

Validation loss: lower after the epoch than before on the same rows in early epochs; in later epochs a small rise is
normal; the held-out evaluation decides.

## 4.8 Export for the serving engine

The serve loads LoRA adapters in Hugging Face PEFT format:

- `adapter_model.safetensors` with keys
  `base_model.model.model.language_model.layers.<N>.self_attn.<proj>.lora_A.weight` and `...lora_B.weight`, for
  `<proj>` in `q_proj`, `k_proj`, `v_proj`, `o_proj`;
- `adapter_config.json` with `r` 16, `lora_alpha` 32, `target_modules` (`q_proj`, `k_proj`, `v_proj`, `o_proj`),
  `lora_dropout` 0.0, `inference_mode` true, `peft_type` `LORA`.

Write these two files directly, or through a converter that only renames keys (check that the round trip
is bit-exact). About 25 MB per adapter. Write the adapter to the shared disk and hand over its absolute
path. Do not merge the adapter into the base each round: that is a 50 GB write and a serve restart,
instead of a load call that takes seconds.

## 4.9 Adapter check

A successful load call does not confirm that the weights are applied; this check does, and it is required.

- Score a fixed answer to a fixed prompt teacher-forced on the serve (`prompt_logprobs`), with the base and with the
  adapter. Do the same in the trainer.
- Use a few rows of different lengths. Compare per-row deltas (adapter minus base, each computed on its own engine),
  not absolute log-probs: absolute log-probs can differ by a few nats between the trainer and the serve.
- Pass: same sign, and |served − trainer| ≤ 0.35 × max(|served|, |trainer|) on rows with |delta| > 3 nats.
- Fail: a served delta near 0.
- Use log-probs, not generated text, for this check.
