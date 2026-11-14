# Hand labelling of 50 hits from run 4 (`hand-label-hits.csv`)

A "hit" in every c-CRAB analysis is a model finding within five lines of the defect line. This sheet
checks whether a hit also states the reviewer's problem. 50 hits, ten per condition (A, B, C, Cx, D),
drawn with `random.Random(0)` from run 4's matched findings and shuffled; the condition column is kept
so the result can be split by condition afterwards, but label without looking at it.

Labelling is done by one author only (Tadael Shewarega), blind. There is no second human labeller.
Files: `labels-blank.csv` (the unlabelled sheet), `labels-tadael-raw.csv` (the author's labels as
submitted), `labels-tadael.csv` (merged into the sheet, with an `ai_point_valid` column), `labels-llm.csv`
(claude-fable-5-1's labels, recorded separately for an agreement check only, not as a second annotator),
`hand-label-summary.txt` (agreement, kappa, Wilson intervals).

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

Recheck (2026-11-14): rows 2 and 34 were labelled `explains` but `ai_point_valid = no`. Row 2 (ray) was set to `ai_point_valid = yes`: the test's `except Exception: pass` means it can never fail, so the model's point holds. Row 34 (pandas) was kept at `ai_point_valid = no` with the note "redundant, not wrong.": `np.isnan` on booleans is always False, so the check is pointless, but the output is still correct. `labels-tadael-raw.csv` keeps the labels as first submitted.
