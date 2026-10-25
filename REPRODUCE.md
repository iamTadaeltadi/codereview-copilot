# Reproducing the paper

Everything the paper reports is recomputed from files in this repository. No
API key is needed unless you want to re-run a model.

## 1. Install (5 minutes)

```bash
git clone https://github.com/iamTadaeltadi/codereview-copilot
cd codereview-copilot
python3.12 -m venv .venv            # 3.10–3.13 work; 3.14 lacks wheels for some deps
.venv/bin/pip install -r requirements-dev.txt matplotlib
```

## 2. Check the numbers (2 minutes, offline)

```bash
PYTHONPATH=.:services/graph:services/agents .venv/bin/python scripts/reproduce.py
```

Every `results/v2*/analysis-*.txt` and `results/ccrab-today/analysis.txt` is
recomputed from the raw per-call records beside it and compared line by line.
The script prints `MATCH` or `DIFF` per file and exits non-zero on any `DIFF`.
Add `--figures` to redraw `paper/figures/`, `--paper` to rebuild
`paper/paper.pdf` (needs Google Chrome for the PDF step).

## 3. Run the tests (3 minutes)

```bash
PYTHONPATH=.:services/api:services/agents:services/graph .venv/bin/python -m pytest tests -q
```

## 4. Where each number comes from

| Paper section | Frozen input | Recompute with |
|---|---|---|
| 4.1 diff-only ceiling | `results/v2-*/analysis-hit.txt` | `experiments/analyse_structure.py <run>/structure-judged-strict.jsonl --metric hit` |
| 4.1 anchor vs evidence | `results/evidence-scope.txt` | `experiments/evidence_scope.py` |
| 4.1 twins | `results/v2twins-*/analysis-correct.txt` | `... --metric correct` |
| 4.2–4.5 arms, judges, precision | `results/v2-*/analysis-{strict-judge,gemini-judge,precise}.txt` | `... --metric mechanism_judge --missing-as-false` / `--metric precise` |
| 4.6 real defects | `results/ccrab-today/*-outcomes.jsonl` | `experiments/analyse_ccrab.py` |
| 4.7 search trigger | `results/search-trigger/` | `experiments/run_search_trigger.py` |
| judge validation | `results/judge-validation-*.json`, `paper/judge-labelling-*` | `experiments/score_labels.py` |

## 5. Re-running a model (optional, costs money)

Put `OPENROUTER_API_KEY=...` in `.env` at the repository root. The runs that
were still waiting on credit when the paper was frozen are listed, in order of
value per dollar, in `experiments/when_credit.sh`. A full eight-arm run on
gpt-4o-mini costs about $3; a frontier model about $40 through batch pricing.
Model versions change, so a re-run reproduces the design, not the exact digits.

## 6. Regenerating the benchmark (optional, needs GitHub)

```bash
.venv/bin/python experiments/rebuild_crossfile.py --trees   # lists repositories, fetches files, verifies evidence
.venv/bin/python experiments/build_twins.py
```

The funnel (candidates, verified, with distractors) is printed. Repositories
drift, so counts will differ from the frozen `data/crossfile-v2.jsonl`.
