# v3 diff-only ceiling check (26 Oct 2026)

Pre-set stop rule (author, 26 Oct): if the diff-only exact-line hit rate on v3 is 95% or higher, stop the queue and report only that.

Run: gpt-4o-mini, tag serialisation, all nine arms, stopped after 201 of 277 defects. Tolerance 0 (exact line). Parse failures: 0 of 1802 replies. Spend: about $0.00.

| arm | n | hit (exact line) | precise (defect is the only flagged hunk) | findings per task | distractors flagged per task |
|---|---|---|---|---|---|
| 1-diff | 201 | 95.5% | 24.4% | 2.66 | 1.58 |
| 2-evidence | 201 | 90.0% | 10.4% | 2.96 | 1.89 |
| 2b-snippets | 200 | 91.5% | 12.0% | 2.94 | 1.81 |
| 3-topology | 200 | 94.0% | 10.5% | 3.00 | 1.88 |
| 4-typed | 200 | 92.5% | 11.5% | 2.93 | 1.82 |
| 5-attributed | 200 | 95.0% | 13.0% | 2.87 | 1.78 |
| 6-corrupted | 200 | 92.5% | 10.5% | 2.96 | 1.82 |
| 7-random | 200 | 97.0% | 30.5% | 2.57 | 1.52 |
| 8-header | 200 | 97.0% | 21.5% | 2.76 | 1.72 |

Diff-only hit by mutation kind: default_flip 104/107, none_sentinel 19/21, tuple_order 58/61, exception_type 6/6, empty_to_none 5/6

Reading: the v3 generator fixes (function-name labels, balanced defect position, syntax-tree-neutral distractors of mixed kinds) did not lower the ceiling. The model reports 2.7 of the 4 hunks per task on average, so the one semantic hunk among cosmetic ones is almost always among them; hit rate cannot separate the arms. The judge-free precision column is the only one that moves, and it moves against the evidence arms. Files: structure-gpt4omini-tag-partial.jsonl (the stopped run, kept whole).
