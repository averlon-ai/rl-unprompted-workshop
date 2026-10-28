---
name: livetest
description: Run and read the security-policy RL live test in this repository — set up the endpoint key, build the dataset, generate and judge the five checkpoints (base, m1, m2, m3, mc), open the notebook, and change the code safely. Use for any task in this repo.
---

Read `AGENTS.md` at the repository root and follow it. The essentials:

- **Credentials come from the user**: `bash save_key.sh` asks for the cynos API key and the judge model and writes
  `.env`. Never guess, print, log or commit the key.
- **Run**: `bash quickstart.sh` (everything, to `results/<UTC>/report.md`) · `bash start_jupyter.sh` (set up, then
  start JupyterLab; `--setup-only` for the setup alone) · `python run_tests.py --check` (connectivity only).
- **Data builds itself** from upstream (`data/build_data.py`) and must match `data/CHECKSUMS`. Never commit
  `data/eval/`, `data/upstream/`, `data/train_policy.jsonl` or `results/`.
- **Withhold a refuse-class reply that is not a full refusal** — a leak may contain harmful model output; the notebook
  shows the request text, and a refuse reply only once a checkpoint fully refuses (`notebooks/nbtheme.py`).
- **The notebook is generated**: edit `notebooks/build_notebook.py`, run
  `python notebooks/build_notebook.py notebooks/livetest.ipynb`, commit it without outputs.
- **Vocabulary**: classes are `comply` / `refuse`; milestones are `base`, `m1`, `m2`, `m3`, `mc`, defined with their
  expected rates in `checkpoints.json`; the headline metric is macro F1.
