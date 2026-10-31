# Working in this repository

This is the operating manual for coding agents (Codex reads it as `AGENTS.md`; Claude Code reads `CLAUDE.md`, which
points here, and has the `livetest` skill) and for people who want the short version. The long version is
`README.md` and `docs/GUIDE.pdf`.

## At a glance

| | |
|---|---|
| Start here | `bash start_jupyter.sh` — set up, then open the notebook in JupyterLab (`--setup-only` for the setup alone) |
| Command line | `bash quickstart.sh` — the same setup, then both stages to `results/<UTC>/report.md` |
| API key | from the user only; created in the Cynos console, https://app.cynos.averlon.ai; starts with `sk-cy-`; `bash save_key.sh` writes `.env` |
| API endpoint | `https://api.cynos.averlon.ai/v1` |
| Judge model | `deepseek/deepseek-v4.1-flash-1017` (`AVN_JUDGE_MODEL`) |
| Milestones | base r0 · m1 r10 · m2 r25 · m3 r80 · mc live — defined in `checkpoints.json` |
| Expected macro F1 | base 55.9 · m1 71.4 · m2 86.1 · m3 89.4 |
| Classes | `comply` / `refuse` (in the data files, `target` is `answer` / `refuse`) |
| Held-out set | 221 comply + 249 refuse, built by `data/build_data.py`; must match `data/CHECKSUMS` |

**What this is.** Five checkpoints of a security-policy RL run are served on one endpoint as `avn_rl_base`,
`avn_rl_m1`, `avn_rl_m2`, `avn_rl_m3` and `avn_rl_mc` (shortened to `base`, `m1`, `m2`, `m3`, `mc`). This repository
puts a held-out validation set through them in two stages — **generate** (every prompt to each checkpoint) and
**judge** (a judge LLM on the same endpoint labels each response *answered / soft refusal / refused*) — and scores
precision, recall and F1 on two classes, **comply** (the policy says answer in full) and **refuse** (the policy says
refuse), with **macro F1** the headline.

## Get it running

1. **Credentials.** The endpoint needs an API key the user creates in Cynos, Averlon's Cyber Inference Platform
   (https://app.cynos.averlon.ai; keys start with `sk-cy-`), and the judge model served on that endpoint,
   `deepseek/deepseek-v4.1-flash-1017` (the default in `.env.example`). Ask the user for the key; never guess,
   generate or paste a key into a file yourself.
   `bash save_key.sh` prompts for them (typed hidden), tests the key and writes `.env` (gitignored, mode 600). No
   script prints the key, and it must never appear in output, logs or commits.
2. **Dataset.** Every entry point builds it automatically (`python data/build_data.py`): the upstream sources are
   downloaded at pinned revisions, the rows named in `data/manifest.jsonl` are taken and verified by hash, and
   `data/eval/policy_unblock.jsonl` (221 comply), `data/eval/policy_block.jsonl` (249 refuse) and
   `data/train_policy.jsonl` are written — byte-identical to `data/CHECKSUMS`. Needs network once; downloads are
   cached in `data/upstream/`. The prompts are not redistributed: never commit `data/eval/`, `data/upstream/` or
   `data/train_policy.jsonl`.
3. **Run.** Start with the notebook:
   - `bash start_jupyter.sh` — **the first step**: sets up the venv, dependencies, kernel and dataset, then starts
     JupyterLab with the notebook open (`--setup-only` does the setup without starting it).
   - `bash quickstart.sh` — the command-line alternative: the same setup, an endpoint check and both stages; result in
     `results/<UTC>/report.md`.
   - `python run_tests.py --check` — connectivity only: one short answer from each checkpoint.
   - Stage by stage: `python generate.py` then `python judge.py` (flags in each file's docstring).

   The notebook, top to bottom: setup and key → the milestones with their expected numbers → connectivity → 3a the
   slice → 3b one run cell per checkpoint, each showing that checkpoint's reply to every request in the slice
   (comply with full text; refuse withheld until judged; the showcase ones marked) → 3c judge → 3d load the run → 3e the gallery across the
   milestones → 4 results (scorecard and F1 chart; set against the expected numbers only for a random or full sample, never the curated slice) → browse, try your own prompt,
   re-judge.

## Reading results

- `results/<UTC>/metrics.json`, per checkpoint: `macro_F1`, `comply_P` / `comply_R` / `comply_F1`, `refuse_P` /
  `refuse_R` / `refuse_F1`, plus the raw rates `over_refusal` (comply requests not answered in full, %) and
  `block_leak` (refuse requests answered, %). `report.md` has the table and the plots; `labels.jsonl` the judge's
  label and reason per response.
- The expected numbers for each frozen milestone are in `checkpoints.json` (`over_refusal`, `block_leak` per
  checkpoint; `avn_client.reference()` derives the P / R / F1). `mc` is the live run and has none.
- One draw at temperature 1.0 is noisy: read the direction `base` → `m3`, not single figures. The notebook's slice is
  chosen from requests the stock model gets wrong, so `base` scores near zero on it by construction, and it is far too small to compare with the expected numbers.
  For that, run `python run_tests.py --all` (or a random `--per-class N`); `generate.json` records how a run was sampled.

## Rules

- **Never print, log or commit the API key** (`CYNOS_API_KEY`). Never commit `.env`.
- **Withhold a refuse-class *reply* that is not a full refusal** — a leak may contain harmful model output; the
  notebook shows it only once a checkpoint fully refuses (`notebooks/nbtheme.py`). The request text is shown in the
  notebook (it is benchmark data). In chat or logs, refer to refuse-class prompts and leaked replies by id rather than
  pasting their text.
- `notebooks/livetest.ipynb` is **generated**: change `notebooks/build_notebook.py` (and `nbtheme.py` for the look),
  then `python notebooks/build_notebook.py notebooks/livetest.ipynb`. Commit the notebook **without outputs** only.
- `checkpoints.json` is the one place that defines the milestones (round, epoch, expected rates). Change it only when
  the served checkpoints change; nothing else hard-codes them.
- The class labels are `comply` / `refuse` everywhere. "Unblock / block" is the policy's own vocabulary
  (`data/policy.md`) for the same two classes and is not used as a label elsewhere. In the data files, `target`
  (`answer` / `refuse`) is the same label in the spelling the code uses.
- `docs/GUIDE.pdf` is a built artifact; its source is not in this repository.
- Generation settings are fixed to what the models were trained and evaluated under (temperature 1.0, top_p 0.95,
  top_k 64, thinking off, no system prompt); do not change them when comparing checkpoints.

## Layout

| | |
|---|---|
| `avn_client.py` | endpoint client, key handling, the judge rubric, metrics, the slice and showcase selection |
| `generate.py` · `judge.py` · `run_tests.py` | stage 1, stage 2, both in one command |
| `plots.py` | charts and the scorecard (matplotlib for the report, plotly for the notebook) |
| `notebooks/` | `livetest.ipynb` (generated), `build_notebook.py` (its source), `nbtheme.py` (its look) |
| `data/` | `manifest.jsonl`, `averlon/own_osp.jsonl`, `build_data.py`, `CHECKSUMS`, `DATA_PROVENANCE.md`, `policy.md` |
| `checkpoints.json` | the five milestones: served name, round, epoch, expected rates |
| `docs/GUIDE.pdf` | the guide |
| `rl-package/` | design package for rebuilding the training yourself (no training code); start at `rl-package/README.md` |
| `quickstart.sh` · `start_jupyter.sh` · `save_key.sh` | the three entry points |
