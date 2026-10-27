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

Every `results/v2*/analysis-*.txt`, `results/v3twins-*/analysis-*.txt` and `results/ccrab-today/analysis.txt` is
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
| 4.1 ceiling, second version | `results/v2-tag-gpt4omini/analysis-hit.txt` | `experiments/analyse_structure.py <run>/structure-judged-strict.jsonl --metric hit` |
| 4.1 ceiling, third version | `results/v3-ceiling/structure-gpt4omini-tag-partial.jsonl` | `results/v3-ceiling/README.md` lists the per-arm table; `scripts/reproduce.py` recomputes it |
| 4.1 ceiling, real defects | `results/ccrab-today/A-outcomes.jsonl` | `experiments/analyse_ccrab.py` |
| 4.2 anchor vs evidence | `results/evidence-scope.txt` | `experiments/evidence_scope.py` |
| 4.3 safe twins, both prompts | `results/v3twins-*/analysis-correct.txt` | `experiments/analyse_structure.py <run>/structure.jsonl --metric correct` |
| 4.4 test verification | `results/test-verified/verify.jsonl`, `summary.txt` | `experiments/verify_by_tests.py` (hours; needs network) |
| 4.5 real defects, incl. the seed-stripped control | `results/ccrab-today/*-outcomes.jsonl` | `experiments/analyse_ccrab.py` |
| 4.6 search trigger | `results/search-trigger/` | `experiments/run_search_trigger.py` |
| 3.2 audit of the released benchmark | `results/audit/v3-recheck.txt` | `experiments/audit_v2.py data/crossfile-v3.jsonl data/crossfile-v3-twins.jsonl --label v3` |
| withdrawn second-version runs (not reported) | `results/v2-*/analysis-*.txt`, `results/WITHDRAWN-v2-structure.md` | as above, kept for audit |

## 5. Re-running a model (optional, costs money)

Put `OPENROUTER_API_KEY=...` in `.env` at the repository root. `experiments/when_credit.sh` lists the runs in order of value per dollar; the
third-version base run was stopped under the ceiling rule after about $0.40. A
full nine-arm run on gpt-4o-mini costs about $0.60; a frontier model about $40
through batch pricing.
Model versions change, so a re-run reproduces the design, not the exact digits.

## 6. Regenerating the benchmark (optional, needs GitHub)

```bash
.venv/bin/python experiments/_fetch_sources.py                       # pools at the pinned commits -> .pool-cache/
.venv/bin/python experiments/rebuild_crossfile.py --from-pools --out data/crossfile-v3.jsonl --per-repo 8
.venv/bin/python experiments/build_twins.py --out data/crossfile-v3-twins.jsonl --per-repo 8
PYTHONPATH=.:services/graph:services/agents .venv/bin/python experiments/audit_v2.py data/crossfile-v3.jsonl data/crossfile-v3-twins.jsonl --label v3
```

The funnel (candidates, verified, with distractors) is printed, and the audit
must report 0 unresolved imports, 0 tree-changing distractors and 0 unsafe
twins. The pools are pinned to commits, so regeneration is deterministic up to
the seeded distractor placement.
