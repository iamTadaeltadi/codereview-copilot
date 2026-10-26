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

## Second benchmark (`data/crossfile-v2*.jsonl`): withdrawn 26 Oct 2026

`v2-*/` and `v2twins-*/` are the held-constant-evidence runs on the second
generated benchmark. Every number from them is withdrawn after an external
review found five instrument defects; see `WITHDRAWN-v2-structure.md` and
`audit/v2-recheck.txt`. Kept whole so the withdrawal can be checked.

## Third benchmark (`data/crossfile-v3*.jsonl`): standing

| Directory | What |
|---|---|
| `audit/v3-recheck.*` | the released benchmark re-checked with the generator's own resolver and tree comparison: 0 / 0 / 0 |
| `v3-ceiling/` | the diff-only ceiling run, stopped at 201 of 277 defects under the pre-set 95% rule; all nine arms kept, arm comparisons not reported |
| `v3twins-tag-gpt4omini/`, `v3twins-tag-deepseek/` | safe twins, nine arms, two models; `analysis-correct.txt` is the clear rate per arm |
| `test-verified/` | each repository's own tests run before and after each mutation; `summary.txt` has the funnel |
