# c-CRAB on google/gemini-2.5-flash — PARTIAL (29 October 2026)

Thinking off (`OPENROUTER_REASONING='{"enabled": false}'`), numbered diff, otherwise the settings
of `results/ccrab-numbered/`. Planned: A, B, Cx on all 195 tasks. Recorded before the API key hit
its $5.00 lifetime cap at 10:13 and every request returned HTTP 403: A and B on the first 60 tasks
in task-id order (75 defects), Cx none. The key cap, not the $3.00 stop rule, ended the run;
spend on this stream was $0.46 (`cost.log`, `launcher.log`, `smoke-raw.jsonl` is the one-task
smoke test). The 403 replies are logged in `main-run.log` and `Cx-run.log` and nothing from them
is recorded, so a relaunch with the same names resumes from here.

| condition (75 defects) | tol 5 | chance | exact | chance | quoted-token exact line |
|---|---|---|---|---|---|
| A diff only | 53.3% | 27.7% | 29.3% | 3.5% | 82.0% |
| B graph | 45.3% | 26.6% | 26.7% | 3.2% | 88.6% |

Both above chance with intervals excluding zero. B − A: −8.0 points, repository bootstrap
[−15.5, −1.1], task bootstrap [−16.0, −1.3]; at exact line −2.7 [−9.4, +4.1]. On 60 tasks only;
no Cx, so the pre-registered primary comparison is not available.

Files as in `results/ccrab-numbered/` (`analysis.txt`, `analysis-exact.txt` by
`experiments/analyse_ccrab_subset.py`; `chance-baseline.txt`; `line-accuracy.txt`).
