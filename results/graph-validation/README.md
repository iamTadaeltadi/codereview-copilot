# Caller validation of the code graph on repositories outside the c-CRAB task set

Run 27 Oct 2026 by `experiments/validate_graph.py` (seed 0, up to 80 files per
package, up to 50 sampled definitions per repository). Ground truth: jedi 0.20.1
`get_references` on the same files, a reference counting as a call when its
line holds a call to the name; the caller is the enclosing function. The old
builder is the module at commit 14c5984; the new one is the current module.
PostHog is in c-CRAB, so it is taken at a current commit and a package
(`posthog/hogql/`) that no task touches; the other five are not in c-CRAB.
`summary.txt` is the table, `<repo>.json` holds every sampled function with
its jedi callers and each builder's callers. Nothing was tuned on c-CRAB tasks.
