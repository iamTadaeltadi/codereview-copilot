# Method

The question is whether telling a model how retrieved code is connected helps it find a defect, once the code itself is already in front of it. Prior comparisons cannot answer this because retrieval and representation change together: a graph-based system retrieves different snippets *and* presents them differently, so a gain cannot be attributed to either. We hold the snippets constant and intervene only on the metadata that describes their relationships.

## 3.1 Task

A reviewer receives a pull-request diff and must report defects as a list of `(file, line, message)`. Each task contains exactly one defect, introduced by a mutation in one file, that is wrong only because of an assumption a different file makes. The diff also contains two or three harmless edits, so the reviewer must say *which* change is wrong rather than *that* something is.

## 3.2 Benchmark construction

Tasks are generated from production repositories at a fixed commit. For every public function with a caller in another file, the generator attempts one of five mutations and keeps the task only when the caller's syntax tree demonstrates the dependency the mutation breaks:

| Kind | Mutation | What the caller must contain |
|---|---|---|
| `exception_type` | `raise A` → `raise B` | a handler that catches `A` and not `B`, enclosing the call |
| `none_sentinel` | `return None` → `return -1` | a comparison of the call's result with `None` |
| `default_flip` | `p=True` → `p=False` in the signature | a call that omits `p`, positionally and by keyword |
| `tuple_order` | `return a, b` → `return b, a` | an unpacking assignment of the call's result |
| `empty_to_none` | `return []` → `return None` | iteration over, or `len` of, the call's result |

Calls are resolved through imports: a bare name imported from the defining module, or `module.name` after a module import. Attribute calls on arbitrary objects are not matched, which excludes most methods and removes name collisions between unrelated functions called `run` or `write`. Each task records the verified caller line and the *argument* of the dependency: the exception type, the parameter name, the unpacked names.

Distractors are rewrites that cannot change behaviour, such as `dict()` → `{}` or `== None` → `is None`. Each is applied to a copy of the whole file and rejected unless the file still parses. The diff lists the defect and the distractors in line order with nothing marking which is which.

An earlier version of this benchmark is withdrawn. Its distractor rewriter broke docstrings in 145 of 204 tasks, so a model that flagged a syntax error was scored as a false positive, and its evidence was located by a regular expression within eight lines of any same-named call, which was a genuine demonstration of dependency in roughly a third of tasks. Section 6 reports the figures. The present generator was written against those findings, and a test suite pins each of them.

## 3.3 Evidence set

For every task the evidence set E is fixed and identical across the arms that receive it: a 25-line window around the mutated line in the definition file, a 25-line window around the verified caller line, and a decoy, which is another function from the definition file at least 24 lines from the defect. Snippets are rendered in a canonical order by path and line, with a header naming the file and line range, so that serialisation order cannot act as a treatment [arXiv:2402.07140]. The decoy exists so that a corrupted relation has a plausible wrong endpoint rather than a self-loop.

## 3.4 Arms

Every arm receives the same diff and the same instructions. Arms 2 to 6 receive the same E and differ only in a metadata block placed after the snippets under a fixed header and a one-sentence explanation of its format.

| Arm | Snippets | Metadata block |
|---|---|---|
| 1 diff only | none | none |
| 2 evidence | E | the attributed block with every token scrambled: file stem, line number, relation kind, argument |
| 3 topology | E | `caller --depends-on--> definition` |
| 4 typed | E | `caller --catches--> definition` |
| 5 attributed | E | `caller --catches(TypeError)--> definition` |
| 6 corrupted | E | the attributed block with the target moved to the decoy |
| 7 random | three snippets from repositories not in the benchmark | none |
| 8 header | none | the scrambled block, under the same header |

Arm 2 is the control for structure. It matches arms 3 to 6 in token count, vocabulary shape and syntax, and states nothing true. Scrambling the line number matters: the snippet headers name their line ranges, so an intact line number identifies a snippet and the topology is recoverable from it. Arm 6 is the negative control: if the model uses the metadata at all, a false relation should cost something. Arm 7 is the relevance control for the snippets themselves, drawn from `requests`, `click` and `rich` so that it cannot contain the evidence by accident. Arm 8 separates the effect of the snippets from the effect of a dependency section being present.

The pre-registered primary comparison is arm 3 against arm 2 on the mechanism metric defined below. Arm 6 against arm 2 is the secondary. All other pairs are exploratory and reported together under a Holm adjustment.

## 3.5 Serialisation

The same relations are rendered two ways, because graph-reasoning accuracy is known to depend on encoding [arXiv:2511.10234]: a flat arrow line and an XML-style tag `<dependency type="catches" argument="TypeError" source=… target=…/>`. A prose rendering exists in the code and was run only on the withdrawn benchmark. A result that appears under one encoding only is reported as a result about that encoding.

## 3.6 Metrics

*Judge.* The mechanism judge is a separate model asked, blind to arm and snippets, whether the message names a concrete fact about the caller. The first judge was deepseek-v3.2, which is also one of the three reviewed models; every run is therefore re-judged by a fourth family, gemini-2.5-flash, and both verdicts are released. Validation against 40 hand-labelled messages is in Section 6.

*Hit*: a finding's line equals the defect line. *Precise*: hit, and no finding on a distractor line. *Mechanism*: hit, and the message on the defect line names what the caller depends on. Mechanism is a per-kind keyword rubric; for `exception_type` the message must contain the old exception name and one of *caller*, *catch*, *except*, *handle*. It is mechanical and auditable, and it is crude: a message can satisfy it by accident, and a correct explanation phrased unusually can fail it. The rubric and every scored message are released. A finding on the right line for the wrong reason, which an earlier version counted as a hit, fails mechanism.

## 3.7 Comprehension probe and hidden-evidence variant

A null on the primary comparison has two readings: the model does not use the structure, or the serialisation failed to convey it. Before interpreting any result, each arm's block is shown alone and the model is asked which identifier the source depends on. A block the model cannot read back is a failure of encoding, not of structure.

A second reading of a null is that the relation was already visible in the snippets, so stating it adds nothing. In the hidden-evidence variant the caller window is taken from the lines above the demonstrating line, so the call is visible and the handler or the `None` check is not. Only `exception_type` and `none_sentinel` admit this, because for the other kinds the demonstrating line is the call itself.

## 3.8 Models, budget and statistics

Three model families at temperature 0.1: gpt-4o-mini, llama-3.3-70b and deepseek-v3.2. Prompt length across arms 2 to 6 is within a few characters by construction and is recorded per call. Tasks are paired across arms; the reported interval is a percentile bootstrap that resamples repositories rather than tasks, because several tasks share a repository and a definition file, with the task-resampled interval shown beside it. McNemar's exact test on discordant pairs is reported for each comparison. Duplicate task–arm rows from resumed runs are dropped, first occurrence kept, and the count is reported. The analysis script is part of the artifact.
