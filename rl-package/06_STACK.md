# 6. Libraries, versions and operations

## 6.1 Two Python environments

Keep the serving engine and the trainer in separate environments; vLLM pins its own torch build.

- **serve + loops**: `vllm==0.26.0` with the torch 2.11 build its wheel installs, `transformers==5.14`, `openai` 2.x,
  `httpx`, `datasets`. The sampler, evaluator and judge client also run here.
- **train**: `torch==2.11`, `transformers==5.13`, `safetensors`, `datasets`. Gemma 4 needs transformers 5.x; PEFT is
  not needed (`04_TRAINING.md` §4.1).

Install `vllm==0.26.0`, then pin `transformers==5.14`; that is the supported pair for Gemma 4. Do not install another
torch over the one vLLM's wheel brings. Use Python 3.10 or later in both environments.

## 6.2 Components

- **Serving:** vLLM, for fast batched sampling with runtime LoRA loading (`05_SERVING.md`).
- **Training:** plain PyTorch + transformers, a small LoRA module of your own and a short training loop. One GPU
  holds the bf16 model with an attention-only LoRA; distributed training is not needed. The default attention
  implementation (SDPA) is enough.
- **Judge client:** the `openai` client or plain `httpx` against OpenRouter's OpenAI-compatible endpoint
  (`https://openrouter.ai/api/v1`), with `usage: {include: true}` to count dollars per batch. Read the API key from
  the environment; never print or log it.

## 6.3 Trainer requirements

Whatever you train with, it must:

- (a) attach LoRA to the language model's attention projections, selected by path, leaving the vision and audio
  towers untouched (`04_TRAINING.md` §4.1);
- (b) restrict the loss to the answer tokens after `<channel|>` (`04_TRAINING.md` §4.2);
- (c) keep the adapter, the optimizer state and the step count across rounds (`04_TRAINING.md` §4.6);
- (d) fit the 262k-token output layer in memory (`04_TRAINING.md` §4.5);
- (e) export PEFT-format adapters (`04_TRAINING.md` §4.8).

## 6.4 Orchestration and process hygiene

- Run a watchdog that keeps the loops and the serve running (restarts any that exit). Any process supervisor works.
- Run each loop under a lock file and a PID file. Each program writes its own PID from inside the program; for vLLM,
  record the PID of the process listening on its port once it is up.
- Stop processes by the PID in their PID file, never by pattern.
- To change a script a loop is running, write a new file and move it into place.
- Write control files atomically (write a temporary file, then rename).
- On a network filesystem, allow about 2 minutes for the first `import transformers` in a fresh environment and set
  startup timeouts above that.
- Load the tokenizer once in the main thread before starting worker threads.

## 6.5 If you run on an ARM (aarch64) system such as GH200

- vLLM 0.26 has aarch64 wheels.
- Set `FLASHINFER_DISABLE_VERSION_CHECK=1` (the aarch64 flashinfer packages carry slightly different version numbers).
- Put the environment's `bin/` first on `PATH` (flashinfer's JIT needs `ninja`).
- On systems where the OS page cache shares GPU memory, drop the page cache before starting the trainer (needs root):
  `sync; echo 3 > /proc/sys/vm/drop_caches`.
