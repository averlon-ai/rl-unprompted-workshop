# 5. Serving

Serve with vLLM on its own GPU. The same server handles sampling, probe continuation, ISR revisions and held-out
generation, for the base model and for every adapter.

## 5.1 Base model on the serve

Serve the bf16 base (`google/gemma-4-26B-A4B-it`, about 49 GB) on the dedicated serve GPU, with
`--gpu-memory-utilization` about 0.88. The rest of that memory goes to the KV cache.

## 5.2 Settings (vLLM 0.26)

```
--max-model-len 8192
--gpu-memory-utilization 0.88
--max-num-seqs 256
--max-num-batched-tokens 16384
--enable-chunked-prefill
--enable-prefix-caching
--enable-lora --max-lora-rank 16 --max-loras 4
--lora-target-modules q_proj k_proj v_proj o_proj
--language-model-only                     (skip the vision and audio towers)
--reasoning-parser gemma4
--generation-config auto                  (use the model's own sampling defaults)
--trust-remote-code
--tensor-parallel-size 1
```

Gemma 4's `generation_config.json` lists three end-of-sequence ids (1, 106, 50); `--generation-config auto` makes
vLLM stop on all of them.

Environment:

- `VLLM_ALLOW_RUNTIME_LORA_UPDATING=True` enables runtime adapter loading.
- `VLLM_SERVER_DEV_MODE=1` enables `/reset_prefix_cache`.

## 5.3 Loading adapters at runtime

- `POST /v1/load_lora_adapter {"lora_name": "run1-r12", "lora_path": "/abs/path/to/adapters/r12"}`
- `POST /v1/unload_lora_adapter {"lora_name": "run1-r3"}`
- `GET /v1/models` lists the registered adapters.
- Then request with `"model": "run1-r12"`.

Registered adapters are the ones the server knows by name, loaded through the API. `--max-loras 4` is the number of
GPU LoRA slots, the adapters that can run in one batch; vLLM swaps registered adapters into those slots on demand.

- Load an adapter only if it is not already registered ("ensure"), always by absolute path.
- Keep the newest 8 adapters registered and unload only older ones. The sampler and the evaluator use the serve at the
  same time; never unload an adapter that another loop may still be using.

## 5.4 Requests

- Send every generation request (sampling, probe continuation, ISR revision, evaluation) to
  `/v1/completions` with the prompt you rendered yourself with the chat template, thinking off. The trainer
  builds its rows from the same rendering, so training and sampling see the same template, and probe
  continuation needs the completions endpoint anyway.
- Send `add_special_tokens: false` with every completions request on a rendered prompt. The rendered text already
  starts with `<bos>`, and the endpoint adds another one by default.
  - Check: send `return_token_ids: true`; the ids are in `choices[i].prompt_token_ids`. The first id is 2 (`<bos>`)
    and the second is not 2.
- Pass `top_k` through the request's extra parameters. Ask for `n = k` samples in one request.
- Run 48-64 concurrent requests; the server batches them.

## 5.5 The prefix cache

vLLM's prefix cache is keyed by the adapter name. Give each adapter a name that is unique across runs (for example
prefixed with the run name). If you load new weights under an existing name, call `POST /reset_prefix_cache` first.
Unload a previous run's adapters before starting a new run.
