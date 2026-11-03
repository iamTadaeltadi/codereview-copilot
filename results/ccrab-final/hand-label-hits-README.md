# Hand labelling of 50 hits from run 4 (`hand-label-hits.csv`)

A "hit" in every c-CRAB analysis is a model finding within five lines of the defect line. This sheet
checks whether a hit also states the reviewer's problem. 50 hits, ten per condition (A, B, C, Cx, D),
drawn with `random.Random(0)` from run 4's matched findings and shuffled; the condition column is kept
so the result can be split by condition afterwards, but label without looking at it.

Columns: `reference_comment` is the human review comment (the ground truth); `model_finding` is the
model's matched finding; `defect_line` / `model_line` / `line_distance` say where each sits; `hunk` is
the reviewed hunk for context. Fill `label` with one of:

- `explains` — the finding raises the same problem the reviewer raised (same cause or same consequence,
  not necessarily the same words);
- `wrong-reason` — right place, a different problem (style, a hypothetical, a generic worry);
- `partial` — overlaps the reviewer's point but misses the mechanism, or names the symptom only;
- `unclear` — the reference comment itself does not state a problem clearly enough to judge.

`note` is free text. Report: the share `explains` over the 50, with a Wilson interval, and the split
by condition; this becomes the "right line, right reason" rate the paper lacks (4.5, limitations).
