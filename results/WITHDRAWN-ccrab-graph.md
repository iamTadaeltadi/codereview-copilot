# Withdrawn: the c-CRAB graph-retrieval result (27 October 2026)

The claim: on 219 test-verified c-CRAB defects, graph retrieval that reaches
the depended-on caller localises 48.4% against 33 to 36% for the diff alone and
for random or lexical retrieval at the same budget (`results/ccrab-today/`,
paper Section 4.5 in the draft of 26 October).

What was wrong: the graph condition's tool returned the seed node, the
function whose line range covers the ground-truth defect line, with its
`line_range` and `metadata`; the random and lexical tools returned the seed
with its name, type and path only. The graph condition alone was therefore
told the span of the function containing the defect, and a hit is any finding
within five lines. Found by an external reviewer on 27 October 2026.

The control: the graph condition with the seed reduced to the entry the other
conditions carry (`experiments/run.py --conditions B --strip-seed`, same
model, budget, tolerance and defects; `results/ccrab-Bs-gpt4omini/`,
`results/ccrab-today/Bs-outcomes.jsonl`). On 223 paired defects (A, C′, Bs and B):

    diff only                      33.2%
    random, other files only       33.2%
    graph, seed stripped           34.1%
    graph, as reported             48.4%

    graph - graph seed-stripped    +14.3  [+8.8, +19.8]  excludes zero
    graph seed-stripped - diff     +0.9   [-3.1, +5.1]   spans zero
    graph seed-stripped - random   +0.9   [-2.9, +4.9]   spans zero

At zero tolerance the stripped condition hits 2.9%, the diff alone 2.5%, the
reported graph condition 9.4%. The fourteen-point gain was the seed span, not
the retrieved neighbours. Every number from the graph condition in
`results/ccrab-today/B-outcomes.jsonl` is withdrawn; the files are kept so the
withdrawal can be checked. The diff-only, random, lexical and whole-file rates
stand, and they are what the paper now reports: on real defects, no budgeted
retrieval condition in this project beats the diff alone.
