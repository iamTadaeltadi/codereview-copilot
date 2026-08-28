# Artifact

Everything required to reproduce the study is available.

## Structure

```
experiments/
  benchmark.py   ground truth loading and the inclusion criteria
  matcher.py     one outcome row per defect per condition
  metrics.py     cluster bootstrap, McNemar, effect sizes with intervals
  power.py       the power simulation
  config.py      the pinned run matrix, models and costs
  llm.py         provider client with per-call token and cost accounting
  review.py      prompts, parsing, truncation guards
  sparse.py      graph construction over a low-bandwidth link
  repo.py        whole-repository graph construction
  run.py         the runner, resumable
  analyse.py     the reported tables, with LaTeX output
results/
  gpt-4o-mini/   outcomes, per-review records, analysis, configuration
  llama-3.3-70b/ the same for the second model family
  depth-ablation/
data/            the benchmark inputs, with provenance
```

## Reproducing

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
python scripts/check_env.py            # names any missing configuration
python experiments/run.py --limit 400 --conditions A,B,C,D,E,F,G \
       --model openai/gpt-4o-mini --name replication
python experiments/analyse.py runs/replication --bootstrap 3000 --latex
```

A run streams to `runs/<name>/` and resumes from what is already recorded, so
an interrupted run continues rather than restarting.

## Verification

The suite covers the properties the study depends on rather than only the code
paths. Among them:

- no honest condition can observe the oracle's targets, whatever is passed to
  the tool factory
- the depth-*k* neighbourhood equals the set of nodes within *k* undirected
  hops, checked against networkx's own shortest-path computation
- no condition exceeds its budget, every condition uses at least 85% of it, and
  the spread between arms stays within a tenth of the budget
- the graph arm never delivers more than 1.35× the text of any other arm
- a comparison whose interval spans zero never reports "no difference"
- a task missing from one condition is excluded from all

```bash
bash scripts/test.sh
```

CI runs the same suites on every push.

## Licensing

Apache-2.0. The repository graph service is derived from RepoGraph
(arXiv:2410.14684, Apache-2.0); see `NOTICE` for the attribution and the list of
changes. Benchmark inputs are from c-CRAB (arXiv:2603.23448, CC BY 4.0).
