# Benchmark inputs

Both files come from the c-CRAB public release
(https://github.com/c-CRAB-Benchmark/dataset, CC BY 4.0), described in
*Code Review Agent Benchmark*, arXiv:2603.23448.

- `stage3_testgen_verified.jsonl` — 339 pull-request instances whose generated
  tests were verified fail-to-pass, with the reference review comments retained.
- `testgen_combined.zip` — the generated tests themselves, one directory per
  instance, each with a `result.json` recording per comment: its `comment_type`
  (functional / style / documentation / structural), the test code, and the
  `before_passed` / `after_passed` / `success` verification verdict.

The ground truth used in this study is the intersection: comments that are
**functional** and whose test **verified** (failed before the fix, passed
after). That is 524 defects across 277 tasks.

The classification and the tests were produced by GPT-5.2 in the c-CRAB
pipeline, so this is not purely human ground truth. It is materially stronger
than a purely model-labelled benchmark, because every retained label is backed
by an executed test that actually flipped from failing to passing — a
machine-checked fact rather than a model's opinion. This is stated in the
paper's Limitations.
