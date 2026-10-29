# c-CRAB final pre-registered run (30 October 2026)

The run pre-registered in `paper/PLAN.md` §11 (commits bd0d1c6, fbcb3ef), executed once. No further
c-CRAB iteration follows it. Same tasks, defects, model and settings as `results/ccrab-numbered/`
(195 tasks, 246 defects, 63 repositories, gpt-4o-mini, temperature 0.1, seed 0, numbered diff,
code payloads of 3,000 tokens for B/C/Cx/D, diff-derived seeds, `-v2` graph cache) with the four
changes of §11, identical for every condition except entity selection:

1. retrieved entities rendered as plain code blocks under a `### path :: name (type)` header
   (`experiments/run.py::render_context`), not JSON;
2. delivered entity ids logged per call (`delivered_ids`, `delivered_seeds` in `*-raw.jsonl`);
3. graph condition B: test files excluded from neighbours, direct callers of changed functions
   ranked first, then callees, then depth 2; class-level seeds dropped when their methods are
   already seeds. By the §11 amendment, C and Cx draw from the same test-free pool, so B and Cx
   differ only in graph structure and ranking. D (lexical) is unchanged;
4. evidence recall reported per condition (`evidence-recall.txt`).

**Primary comparison, fixed before the run** (`analysis-primary-subset.txt`): B − Cx on the
localised rate at tolerance 5, on source-file defects whose comment is strict outside-diff
(`primary-subset.txt`, 77 ids committed before the run; 64 paired here, 34 repositories).

| subset: strict outside-diff, source files (n = 64) | B graph | Cx random other files | A diff only | C random any | D lexical |
|---|---|---|---|---|---|
| localised, tolerance 5 | 64.1% | 51.6% | 51.6% | 54.7% | 54.7% |
| exact line | 34.4% | 31.2% | 32.8% | 32.8% | 32.8% |

B − Cx = **+12.5 points**, repository bootstrap [+5.0, +20.8], task bootstrap [+4.7, +20.3];
excludes zero. B localises 8 defects that Cx misses and Cx none that B misses; 7 repositories
favour B, none favour Cx. B − A +12.5 [+3.6, +22.4]; Cx − A 0.0 [−4.5, +4.8]; B − C +9.4
[+2.1, +17.2]; B − D +9.4 [0.0, +18.5]. At exact line B − Cx is +3.1 [−3.2, +9.0], spans zero.

*Disclosure, as in §11.* The subset was seen in exploratory analysis before the plan was written:
on the 29 October records it read B 54.7% against Cx 51.6%, on the 28 October records B 40.6%
against Cx 42.2%. This run is the one pre-registered test of it; the two earlier readings were not.

**Secondary, all defects** (`analysis.txt`, `analysis-exact.txt`, `chance-baseline.txt`): 244 defects
answered in all five conditions. One task (numpy-20310) was skipped in B, C, Cx and D because no
source file could be fetched for its commit; one D reply (marimo-4080) was unparseable JSON.

| condition | localised, tol 5 | random-line chance | exact line | chance | mean findings |
|---|---|---|---|---|---|
| A diff only | 50.8% | 35.3% | 23.4% | 4.8% | 5.07 |
| B graph | 54.1% | 35.4% | 24.6% | 4.9% | 5.05 |
| C random, any file | 52.0% | 34.9% | 24.2% | 4.8% | 5.04 |
| Cx random, other files | 52.9% | 35.1% | 24.6% | 4.6% | 5.07 |
| D lexical | 52.9% | 35.3% | 25.0% | 4.8% | 5.10 |

B − Cx +1.2 [−2.2, +5.0] (task bootstrap [−2.9, +5.3]); B − A +3.3 [−0.9, +7.2]; Cx − A +2.0
[−1.7, +5.2]; C − A +1.2 [−2.3, +4.7]; D − A +2.0 [−1.8, +5.4]; all span zero. Every condition is
above its random-line baseline by 15 to 19 points at tolerance 5 and 18 to 20 at exact line, with
intervals excluding zero. (Exact line in `analysis-exact.txt` is recomputed from the run's
tolerance-5 match; `chance-baseline.txt` re-matches at tolerance 0; they differ by one defect.)

**Line accuracy** (`line-accuracy.txt`, findings quoting a token present in the diff): 72.1% exact,
95.3% within 5 lines, 4.7% more than 5 off, pooled over 2,069 located findings; by condition
69.6% to 74.0% exact.

**Evidence recall** (`evidence-recall.txt`): share of defects whose comment names a file or
identifier found in the delivered context. B 61.9%, D 60.4%, C 50.6%, Cx 50.0%, A 0.0% (no
context). Restricted to the 85 defects whose comment names something outside the diff: D 22.6%,
B 18.8%, Cx 14.1%, C 11.8%.

**Cost.** $0.76 recorded (`cost.log`, `launcher.log`); the $2.00 stop never triggered.

**Files.** `{A,B,C,Cx,D}-outcomes.jsonl` (the `condition` field of `Cx-outcomes.jsonl` reads `C`;
it is the pass run with `--prefer-cross-file`), `{main,Cx,C}-raw.jsonl` with `context_text` and
delivered ids, `{main,Cx,C}-run.log`, `{main,Cx,C}-config.json`, `primary-subset.txt`,
`analysis-primary-subset{,-exact}.txt`, `launch.sh`, and `hand-label-sample.csv` (50 findings,
seed 0, from all 4,912 in this run, same columns as in `ccrab-numbered/`).

**Known limitation, as before.** Methods are keyed without their class (69 of 84 false-positive
caller edges in `results/graph-validation/` were on methods). Not fixed for this run.
