# Condition E: CIS context on c-CRAB, with control CxE (paper/PREREG-E.md)

Status, 6 November 2026: context extracted and coverage reported. **No model has been called.**
The OpenRouter balance was −$0.03, so the runs wait for credit.

CIS at `4ea4bfe9e37b1a91311d88b6ae9797dd2b5f8ea9` (tarball sha256 `c34112bf…3166`), built with
`cargo build --release -p cis-mcp --features python-ast,body-sqlite` (cargo 1.96.0; `cisd` sha256
`ca3e7556…301b`), queried as `cisd --mcp` over stdio, session 0. Per task CIS indexed the source
files of run 4's cached graph, the same files B, C, Cx and D drew from: the diff's files and their
imports, outward, up to 3 hops and 60 files, not the full repository (`file-pool.txt`). CxE, the
size-matched random control of the second amendment, is Cx's own draw cut per task to E's size.

| file | what |
|---|---|
| `coverage.txt` | the step-3 coverage report, from `experiments/cis_coverage.py` |
| `context-E.json` | every raw CIS hit per task before any filter or budget: `{task_id: [{path, start_line, end_line, relation, text}]}` |
| `context-E-records.jsonl.gz` | the full per-task records: seeds, hits, CIS index status, errors, timings |
| `context-E-delivered.json` | the context the model will see, after B's filter, order, cap, 40-line cut and 3,000-token budget |
| `file-pool.txt` | files CIS indexed per task against the full repository and B's files, from `experiments/cis_file_pool.py` |
| `context-CxE-delivered.json` | CxE's context per task, from `experiments/cxe_context.py` |
| `cxe-matching.txt` | the Cx reproduction check and how closely CxE matches E's size |
| `superseded/` | the first extraction, before the file-hub amendment in PREREG-E.md; kept, not used |

Reproduce: `experiments/cis_extract.py`, then `experiments/cis_context.py`, then
`experiments/cis_coverage.py`, then `experiments/cis_file_pool.py` and `experiments/cxe_context.py`. The runs: `experiments/launch_ccrab_cis.sh`. The tests:
`experiments/analyse_ccrab_cis.py`, checked by feeding it run 4's B in place of E, which
reproduces the replication's B − Cx exactly when the frozen B and Cx records are fed in as E and CxE.
