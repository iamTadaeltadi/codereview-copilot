# Results

Each directory holds the raw per-call records of one run and the analysis
output computed from them. Nothing here is edited by hand.

## Withdrawn (kept for audit; do not cite)

`crossfile/`, `crossfile-fixed/`, `structure/` — measured on the first
generated benchmark, `data/crossfile.jsonl`. See the `WITHDRAWN.md` in each.

## Standing

| Directory | What |
|---|---|
| `gpt-4o-mini/`, `llama-3.3-70b/`, `depth-ablation/` | c-CRAB real-defect runs. Condition B (graph) in these predates the retrieval fixes and is not reported; A, C, D, E, F, G stand. |
| `evidence-scope.*` | anchor-vs-evidence classification of 291 c-CRAB defects, strict and loose bounds, reason per decision |
| `search-trigger/` | the search-trigger test, 40 paired tasks |
| `audit/` | the retrieval-comparison audit that withdrew "which code does not matter" |
| `judge-validation-*.json` | 40 hand-labelled messages and the judge's verdicts, used to validate `mechanism_judge` |

## Rebuilt benchmark (`data/crossfile-v2*.jsonl`), runs in `runs/v2*`

Frozen into `results/v2-*/` when complete. Run names: `v2-tag-gpt4omini`,
`v2-flat-gpt4omini`, `v2-tag-llama`, `v2-tag-deepseek` (base, eight arms);
`v2-noise4-gpt4omini` (four unrelated snippets added); `v2-hidden-gpt4omini`
(caller window above the demonstrating line); `v2twins-tag-gpt4omini`
(matched safe twins). Analyse with `experiments/analyse_structure.py`;
`experiments/judge_mechanism.py --strict` adds the validated judge verdict.
