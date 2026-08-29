# Retraction: "random context beats graph retrieval"

Reported earlier from this run. **Withdrawn.** The comparison was not a test of
graph retrieval.

## What was claimed

| Condition | Exactly right |
|---|---|
| no context | 36% |
| graph | 43% |
| **random** | **46%** |

and, against random at the same budget, graph −2.8%, dense −3.4% with the
interval excluding zero. The reading offered was that retrieval relevance is
undetectable.

## Why it does not hold

Three measurements, in order.

**1. The answer was usually absent from the pool.** Sources are gathered by
walking from the diff's files to what *they* import. The caller imports the
definition, not the reverse, so it is not reached. Across 199 tasks the caller
was present in the retrieval pool **96 times (48%)** and absent **103 times
(52%)**.

**2. Restricting to the fair subset does not rescue the result.** On the 83
tasks where the caller was in the pool, graph still trails random by 4.8 points
[−10.8, +0.0]. So the pool alone is not the explanation.

**3. Retrieval was querying the wrong node.** The run passed
`defect.path` — a *file* path — so the query resolved to the file node, whose
neighbourhood is the file's own contents. On the 28 tasks where the caller was
both in the pool and reachable, the retriever returned **28 neighbours on
average and the caller in 1 case out of 28 — 4%**.

## What was actually compared

Same-file retrieval against random retrieval. Neither arm was supplied with the
cross-file dependency the benchmark was built around, so neither could use it,
and the difference between them carries no information about graph retrieval.

## What survives

Nothing about graph retrieval. The other results from this run stand on their
own footing:

- the fault-location oracle behaves as reported, because it does not depend on
  retrieval — it is handed the ground-truth location directly
- the structure experiment is unaffected: it supplies the evidence set
  explicitly and never retrieves
- the anchor-versus-evidence measurement is unaffected

## What has to happen before the comparison is re-reported

Query the defect's *function* node rather than its file, and gather sources so
that files importing the definition are present. Until both hold, condition B
is not graph retrieval and must not be labelled as such.
