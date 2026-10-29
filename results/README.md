# Results

Each directory holds the raw per-call records of one run and the analysis
output computed from them. Nothing here is edited by hand.

## Withdrawn (kept for audit; do not cite)

`crossfile/`, `crossfile-fixed/`, `structure/` — measured on the first
generated benchmark, `data/crossfile.jsonl`. See the `WITHDRAWN.md` in each.

## Standing

| Directory | What |
|---|---|
| `gpt-4o-mini/`, `llama-3.3-70b/`, `depth-ablation/` | August c-CRAB real-defect runs. Condition B (graph) in these predates the retrieval fixes and is not reported; A, C, D, E, F, G stand. |
| `ccrab-today/` | the October c-CRAB re-run: A, C, Cx, D stand; `B-outcomes.jsonl` is withdrawn (`WITHDRAWN-ccrab-graph.md`), `Bs-outcomes.jsonl` is the seed-stripped control |
| `ccrab-Bs-gpt4omini/` | raw records and log of the seed-stripped control |
| `ccrab-v2/` | the pre-registered rerun of 28 Oct after the retrieval repair (PLAN.md §10): A, B, C, Cx, D on 239 paired defects, code payloads, diff seeds, 3,000 tokens; B − Cx −2.5 [−6.0, +1.0] |
| `ccrab-numbered/` | the 29 Oct rerun of `ccrab-v2` with numbered diff lines (PLAN.md §10 amendment): every condition ~50% at tolerance 5, 15 points above its random-line chance; B − Cx +0.8 [−1.3, +3.3]; includes the 50-comment hand-label CSV |
| `ccrab-gemini/` | PARTIAL: gemini-2.5-flash (thinking off, numbered diff) A and B on 60 tasks; key cap stopped it; B − A −8.0 [−15.5, −1.1]; no Cx |
| `v3-neutral-gemini/`, `v3twins-neutral-gemini/` | PARTIAL: gemini-2.5-flash neutral prompt, arms 1/2/5/7, 80 defects + 80 twins; d'/c and balanced accuracy |
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
| `v3twins-tag-gpt4omini/`, `v3twins-tag-deepseek/` | safe twins, nine arms, two models, presuming prompt; `analysis-correct.txt` is the clear rate per arm |
| `v3twins-neutral-gpt4omini/` | the same twins under the neutral prompt (`--neutral-prompt`), gpt-4o-mini |
| `v3-neutral-gpt4omini/` | the 277 defects under the neutral prompt, gpt-4o-mini; `analysis-balanced-with-twins.txt` combines it with the neutral twins into balanced accuracy |
| `v3twins-neutral-deepseek/` | the same twins under the neutral prompt, deepseek-v3.2, three parallel shards of one file (see its README) |
| `test-verified/` | each repository's own tests run before and after each mutation; `summary.txt` has the funnel |
