# Withdrawn, 26 October 2026: every structure and twin result measured on crossfile-v2

An external review of the generator and the arms found, and `results/audit/v2-recheck.txt`
confirms on the data, five defects in the instrument used for Sections 4.1 (twins), 4.2–4.5
and the moderators:

1. **Line-number labels.** Evidence snippets were labelled `stem:line` with the mutated
   line's own number, and the diff's hunk header carries the same number. The true-map
   arms (3, 4, 5) therefore pointed at the answer; the scrambled control (arm 2) did not.
   The topology-versus-control comparison was confounded by a pointer.
2. **Same-name imports.** The resolver accepted `from <any module> import name`. In 36 of
   229 tasks the caller's import does not resolve to the mutated module.
3. **Unsafe twins.** Twin safety was checked only against resolved cross-file callers. In
   25 of 150 twins a call in the definition file or the shown caller itself would be broken
   by the mutation; the pool-wide figure is higher.
4. **Tree-changing distractors.** 91 of 650 distractor hunks change the file's syntax tree,
   including quote rewrites inside docstrings and at least one that merges two code strings.
5. **Parse failures scored as answers.** An unparseable reply produced no findings and was
   scored as correctly silent on twins (102 rows in `v2twins-tag-deepseek`).

The generator and the arms were fixed in commit ee99705 (`tests/test_review_fixes.py` pins
each defect). The benchmark is regenerated from the same pools as `crossfile-v3*.jsonl`
and every arm is re-run before any structure or twin number is reported again. The
directories `results/v2-*` and `results/v2twins-*` are kept so the withdrawal can be
checked; `structure-rescored.jsonl` beside each twin run shows the parse-failure fix alone.

Unaffected: the c-CRAB retrieval result (Section 4.6), the anchor-versus-evidence
measurement, the diff-only ceiling on c-CRAB, and the search-trigger test. The diff-only
ceiling on the generated benchmark (97.8%) is a property of the mutations and stands as a
diagnostic finding, with the number to be restated on v3.
