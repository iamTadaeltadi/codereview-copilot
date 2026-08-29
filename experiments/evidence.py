"""Build the evidence set E for a defect, and the metadata block for each arm.

The study holds E constant and varies only what is said about the relationships
among its snippets. Everything that could vary alongside structure is pinned
here: snippet selection, ordering, formatting, and token count.

Arm 2 is the control that matters. A block of low-signal filler would dilute
attention while a graph string is dense, so a win for the structured arm could
be signal-to-noise rather than topology. Arm 2 therefore receives the *same
graph string with node labels shuffled* — identical token count, vocabulary,
syntax and density, with no recoverable topology.
"""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass, field


ARM_DIFF_ONLY = "1-diff"
ARM_EVIDENCE = "2-evidence"
ARM_TOPOLOGY = "3-topology"
ARM_TYPED = "4-typed"
ARM_ATTRIBUTED = "5-attributed"
ARM_CORRUPTED = "6-corrupted"
ARM_RANDOM = "7-random"

ARMS = (ARM_DIFF_ONLY, ARM_EVIDENCE, ARM_TOPOLOGY, ARM_TYPED,
        ARM_ATTRIBUTED, ARM_CORRUPTED, ARM_RANDOM)

# Arms that receive the identical evidence snippets. The core comparison lives
# entirely inside this set; anything outside it varies more than structure.
EVIDENCE_ARMS = (ARM_EVIDENCE, ARM_TOPOLOGY, ARM_TYPED, ARM_ATTRIBUTED, ARM_CORRUPTED)

FLAT = "flat"
TAG = "tag"
PROSE = "prose"
ENCODINGS = (FLAT, TAG, PROSE)

WINDOW = 12


@dataclass(frozen=True)
class Snippet:
    path: str
    start: int
    end: int
    text: str
    label: str

    def render(self) -> str:
        return f"# {self.path}:{self.start}-{self.end}\n{self.text}"


@dataclass(frozen=True)
class Relation:
    source: str
    target: str
    kind: str
    argument: str = ""


@dataclass(frozen=True)
class Evidence:
    snippets: tuple
    relations: tuple = field(default_factory=tuple)

    def rendered(self) -> str:
        """Canonical order: path then line. Identical across every arm."""
        ordered = sorted(self.snippets, key=lambda s: (s.path, s.start))
        return "\n\n".join(s.render() for s in ordered)


def window(text: str, line: int, radius: int = WINDOW):
    lines = text.split("\n")
    lo = max(1, line - radius)
    hi = min(len(lines), line + radius)
    return lo, hi, "\n".join(lines[lo - 1 : hi])


SOURCE_CACHE = ".source-cache"


def sources_for(task, token: str = "", cache_dir: str = SOURCE_CACHE) -> dict:
    """Fetch exactly the two files E needs, and keep them.

    Import traversal cannot reach the caller: it walks from the diff's files to
    what *they* import, and the caller imports the definition rather than the
    reverse. The evidence set is known by construction here, so the files are
    fetched by name instead of discovered.

    The cache is not an optimisation. Each encoding and each model family is a
    separate run over the same tasks, and on a slow link re-fetching the same
    two files per task turns a twenty-minute run into an overnight one — the
    first tag-encoding attempt produced nothing in ten minutes. Sources at a
    fixed commit never change, so caching them costs nothing in validity.
    """
    import json as _json
    from pathlib import Path as _Path

    from experiments.sparse import fetch_file

    meta = task.metadata or {}
    wanted = [p for p in (task.defects[0].path, meta.get("caller_path", "")) if p]

    cache = _Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{task.repo}@{task.review_commit}::{'|'.join(wanted)}".encode()).hexdigest()
    hit = cache / f"{key}.json"
    if hit.is_file():
        try:
            return _json.loads(hit.read_text())
        except Exception:
            pass

    out = {}
    for path in wanted:
        if path in out:
            continue
        text = fetch_file(task.repo, task.review_commit, path, token=token)
        if text is not None:
            out[path] = text
    if out:
        hit.write_text(_json.dumps(out))
    return out


def evidence_for(task, sources, radius: int = WINDOW) -> Evidence | None:
    """E for a generated cross-file defect: the definition and its caller.

    Known exactly by construction — the generator emitted the task only because
    the caller's own source demonstrates the dependency — which is why the
    mutation set is the right instrument for this comparison even though it
    cannot carry a real-world claim.
    """
    meta = task.metadata or {}
    defect = task.defects[0]
    caller_path = meta.get("caller_path", "")
    caller_line = meta.get("caller_line")
    if not (defect.path and caller_path and caller_line):
        return None

    def find(path):
        if path in sources:
            return sources[path]
        for candidate in sources:
            if candidate.endswith(path) or path.endswith(candidate):
                return sources[candidate]
        return None

    definition_src = find(defect.path)
    caller_src = find(caller_path)
    if definition_src is None or caller_src is None:
        return None

    d_lo, d_hi, d_text = window(definition_src, defect.line, radius)
    c_lo, c_hi, c_text = window(caller_src, int(caller_line), radius)

    definition = Snippet(defect.path, d_lo, d_hi, d_text, _label(defect.path, defect.line))
    caller = Snippet(caller_path, c_lo, c_hi, c_text, _label(caller_path, int(caller_line)))

    # A decoy is required, not optional. With two snippets the only endpoint a
    # corrupted edge can move to is its own source, and a self-loop is nonsense
    # the model dismisses without engaging — which teaches nothing. The decoy is
    # a real function from the definition's own file, identical across every
    # arm, so it cannot confound anything: it only gives corruption somewhere
    # plausible to point.
    decoy = _decoy(definition_src, defect.path, defect.line, radius)
    snippets = (definition, caller) + ((decoy,) if decoy else ())

    kind, argument = _relation_for(meta.get("kind", ""), meta.get("evidence", ""))
    return Evidence(
        snippets=snippets,
        relations=(Relation(caller.label, definition.label, kind, argument),),
    )


def _decoy(source: str, path: str, avoid_line: int, radius: int):
    """Another real function from the same file, far from the defect."""
    lines = source.split("\n")
    candidates = [
        i for i, line in enumerate(lines, 1)
        if re.match(r"\s*def\s+\w+", line) and abs(i - avoid_line) > radius * 2
    ]
    if not candidates:
        return None
    line = min(candidates, key=lambda i: abs(i - avoid_line))
    lo, hi, text = window(source, line, radius)
    return Snippet(path, lo, hi, text, _label(path, line))


def _label(path: str, line: int) -> str:
    stem = path.rsplit("/", 1)[-1].replace(".py", "")
    return f"{stem}:{line}"


def _relation_for(mutation_kind: str, evidence_line: str):
    """The relation the caller has to the definition, and its argument.

    The argument is isolated in arm 5 alone precisely because it can leak: for
    an exception mutation it names the very type that changed.
    """
    kinds = {
        "exception_type": "catches",
        "none_sentinel": "checks-return-of",
        "empty_to_none": "iterates-return-of",
        "tuple_order": "unpacks-return-of",
        "default_flip": "calls-without-argument",
        "normalisation": "compares-return-of",
        "boundary": "depends-on-bound-of",
        "slice_bound": "depends-on-length-of",
        "shared_mutable": "mutates-return-of",
    }
    kind = kinds.get(mutation_kind, "depends-on")
    argument = ""
    match = re.search(r"except\s+(\w+)", evidence_line or "")
    if match:
        argument = match.group(1)
    return kind, argument


# --- metadata blocks -------------------------------------------------------

def _serialise(relations, encoding: str) -> str:
    lines = []
    for r in relations:
        if encoding == FLAT:
            arg = f"({r.argument})" if r.argument else ""
            lines.append(f"{r.source} --{r.kind}{arg}--> {r.target}")
        elif encoding == TAG:
            arg = f' argument="{r.argument}"' if r.argument else ""
            lines.append(f'<dependency type="{r.kind}"{arg} source="{r.source}" target="{r.target}"/>')
        else:
            arg = f" on {r.argument}" if r.argument else ""
            lines.append(f"{r.source} {r.kind.replace('-', ' ')} {r.target}{arg}.")
    return "\n".join(lines)


def _strip_argument(relations):
    return tuple(Relation(r.source, r.target, r.kind, "") for r in relations)


def _to_topology(relations):
    return tuple(Relation(r.source, r.target, "depends-on", "") for r in relations)


def _shuffle_labels(relations, seed: str):
    """Same string, same density, no recoverable information.

    Node labels and the relation argument are both replaced by deterministic
    character permutations, so token count, vocabulary and syntax survive while
    nothing true remains.

    The argument must be scrambled too. Leaving it intact would let the control
    name the very thing the defect turns on — for an exception mutation, the
    argument *is* the answer — and the control would then carry more
    information than the topology arm it exists to be compared against.
    """
    rng = random.Random(hashlib.sha1(seed.encode()).hexdigest())
    labels = sorted({r.source for r in relations} | {r.target for r in relations})
    mapping = dict(zip(labels, [_scramble(l, rng) for l in labels]))
    return tuple(
        Relation(mapping[r.source], mapping[r.target], r.kind,
                 _scramble_word(r.argument, rng) if r.argument else "")
        for r in relations
    )


def _scramble_word(word: str, rng) -> str:
    chars = list(word)
    rng.shuffle(chars)
    return "".join(chars)


def _scramble(label: str, rng) -> str:
    stem, _, line = label.partition(":")
    chars = list(stem)
    rng.shuffle(chars)
    return f"{''.join(chars)}:{line}"


def _corrupt(relations, snippets, seed: str):
    """Plausible wrong endpoints, preserving everything else.

    Edge count, degree, relation types, arguments and length are held; only the
    target moves, and only onto a label present in the evidence. A corruption
    the model can dismiss as nonsense teaches nothing.
    """
    rng = random.Random(hashlib.sha1((seed + "corrupt").encode()).hexdigest())
    labels = [s.label for s in snippets]
    out = []
    for r in relations:
        # Never the true target, and never the source: an edge pointing back at
        # its own origin is a self-loop, which reads as malformed rather than as
        # a wrong claim about the code.
        alternatives = [l for l in labels if l not in (r.target, r.source)]
        target = rng.choice(alternatives) if alternatives else r.target
        out.append(Relation(r.source, target, r.kind, r.argument))
    return tuple(out)


def metadata_block(evidence: Evidence, arm: str, encoding: str = FLAT, seed: str = "") -> str:
    if arm == ARM_EVIDENCE:
        return _serialise(_shuffle_labels(evidence.relations, seed), encoding)
    if arm == ARM_TOPOLOGY:
        return _serialise(_to_topology(evidence.relations), encoding)
    if arm == ARM_TYPED:
        return _serialise(_strip_argument(evidence.relations), encoding)
    if arm == ARM_ATTRIBUTED:
        return _serialise(evidence.relations, encoding)
    if arm == ARM_CORRUPTED:
        return _serialise(_corrupt(evidence.relations, evidence.snippets, seed), encoding)
    return ""


def random_evidence(task, sources, evidence: Evidence, seed: str = "",
                    radius: int = WINDOW) -> Evidence:
    """Arm 7: the same number of snippets, none of them the ones that matter.

    Arms 2-6 vary what is *said* about the evidence. This one varies the
    evidence itself, and it is the control the earlier cross-file run showed to
    be indispensable: random repository code scored higher there than targeted
    retrieval, so a study that omits it cannot tell relevance from presence.

    Snippets are drawn from the same files at positions far from the true
    evidence, so language, style and density match and only the content differs.
    """
    rng = random.Random(hashlib.sha1((seed + "random").encode()).hexdigest())
    avoid = {(s.path, s.start, s.end) for s in evidence.snippets}
    pool = []
    for path, text in sorted(sources.items()):
        lines = text.split("\n")
        for index, line in enumerate(lines, 1):
            if not re.match(r"\s*def\s+\w+", line):
                continue
            lo, hi, body = window(text, index, radius)
            if any(p == path and not (hi < a or lo > b) for p, a, b in avoid):
                continue
            pool.append(Snippet(path, lo, hi, body, _label(path, index)))

    if len(pool) < len(evidence.snippets):
        return evidence
    rng.shuffle(pool)
    return Evidence(snippets=tuple(pool[: len(evidence.snippets)]), relations=())
