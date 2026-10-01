# Withdrawn — 1 October 2026

Every number in this directory was measured on `data/crossfile.jsonl`, the
first generated cross-file benchmark. An independent audit found, and the data
confirms:

- **304 distractor hunks across 145 of 204 tasks do not parse.** The
  quote-style rewrite turned `"""` into `''"`. A model that flagged those lines
  was right; the scorer counted it as a confirmed false positive. The "exactly
  right" metric therefore measured silence about a syntax error.
- **The evidence line called the mutated function in 65/65 `default_flip`
  tasks and 18/139 tasks of every other kind.** Evidence was located by regex
  within eight lines of any same-named call, with no import resolved. "Ground
  truth by construction" was false for two-thirds of tasks.
- **Diff-only found the defect line 93% of the time.** There was no headroom.
- 184 unique task ids in 204 rows; 133 duplicate (task, arm) rows in the
  structure files were counted.

The files are kept so the withdrawal can be checked. Do not cite them.
The rebuilt benchmark is `data/crossfile-v2.jsonl` (`verified: "ast"`), and
its results will live in a separate directory.
