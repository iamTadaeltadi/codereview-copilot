#!/usr/bin/env python3
"""Mine real cross-file regressions from repository history.

    python experiments/mine_regressions.py --repos 20 --out data/regressions.jsonl

The generated benchmark is conditioned on a retrievable dependency existing: it
finds a relation, breaks it, keeps the case only when the relation proves the
break, and then evaluates methods that retrieve that relation. That is a
legitimate controlled instrument and it cannot carry a claim about real
software.

This mines defects nobody designed. A commit is a candidate when a later commit
reverts it or fixes it, and it is kept only when the fix touches a *different*
file than the one that introduced the fault — which is what makes the defect
cross-file rather than local.

Yield is expected to be poor and the funnel is reported rather than hidden.
Separating a genuine regression from a refactor bundled with a fix, or from a
commit that merely exposed an older bug, is the part that cannot be automated
away, so every retained instance records the evidence that placed it there.
"""

from __future__ import annotations

import argparse, json, os, re, subprocess, sys, tempfile, shutil
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# A fix commit announces itself. These are the phrases that do so without also
# matching ordinary feature work.
FIX = re.compile(
    r"\b(fix(es|ed)?|revert(s|ed)?|regression|broke[n]?|breaks?|"
    r"correct(s|ed)?|repair(s|ed)?|bug)\b", re.I)
REVERT = re.compile(r"^Revert\s+\"", re.I)
ISSUE = re.compile(r"#\d+|closes?\s+#\d+|fixes\s+#\d+", re.I)

CODE = {".py", ".js", ".java", ".c"}

# A defect whose only victim is a test is a weaker defect: production code is
# unaffected and a reviewer could reasonably decline to flag it. The same rule
# the generated benchmark applies.
TEST_PATH = re.compile(r"(^|/)(tests?|testing)/|(^|/)test_[^/]*$|_test\.[a-z]+$|conftest\.py$")

# "test: fix broken integration tests" repairs the test, not the code. These
# prefixes announce work that is not a production regression.
NOT_A_REGRESSION = re.compile(r"^(test|ci|docs?|chore|style|build|refactor|bump)\b[:(\s]", re.I)


def is_test(path: str) -> bool:
    return bool(TEST_PATH.search(path or ""))


def run(cmd, cwd=None, timeout=120):
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                             timeout=timeout, check=False)
        return out.stdout
    except Exception:
        return ""


def clone(repo, workdir, depth=4000):
    target = Path(workdir) / repo.replace("/", "__")
    if target.is_dir():
        return target
    url = f"https://github.com/{repo}.git"
    run(["git", "clone", "--filter=blob:none", "--depth", str(depth), url, str(target)],
        timeout=900)
    return target if (target / ".git").is_dir() else None


def files_in(repo_dir, sha, production_only=True):
    out = run(["git", "show", "--name-only", "--pretty=format:", sha], cwd=repo_dir)
    paths = {l.strip() for l in out.split("\n") if l.strip() and Path(l.strip()).suffix in CODE}
    return {p for p in paths if not is_test(p)} if production_only else paths


def parent_of(repo_dir, sha):
    return run(["git", "rev-parse", f"{sha}^"], cwd=repo_dir).strip()


def mine(repo_dir, limit=8):
    """Fix commits whose fix lands in a different file than the change it repairs."""
    log = run(["git", "log", "--pretty=format:%H\x1f%s", "-n", "3000"], cwd=repo_dir)
    entries = [l.split("\x1f", 1) for l in log.split("\n") if "\x1f" in l]

    found = []
    seen_fixes = set()
    for sha, subject in entries:
        if not (FIX.search(subject) or REVERT.match(subject)):
            continue
        if NOT_A_REGRESSION.match(subject):
            continue
        if sha in seen_fixes:
            continue
        # A targeted fix touches few production files. A large one is a
        # refactor with a fix folded into it, and the fault cannot be
        # attributed to any single change in it.
        fix_files = files_in(repo_dir, sha)
        if not (1 <= len(fix_files) <= 2):
            continue
        seen_fixes.add(sha)

        # The commit each fixed line last changed, which is where the fault was
        # introduced. git blame on the parent of the fix gives it.
        parent = parent_of(repo_dir, sha)
        if not parent:
            continue
        introduced = {}
        for path in sorted(fix_files):
            blame = run(["git", "blame", "--line-porcelain", "-L", "1,80",
                         parent, "--", path], cwd=repo_dir, timeout=60)
            for line in blame.split("\n"):
                if re.match(r"^[0-9a-f]{40} ", line):
                    introduced.setdefault(path, set()).add(line.split()[0])

        for path, shas in introduced.items():
            for intro in list(shas)[:6]:
                intro_files = files_in(repo_dir, intro)
                # The introducing change must be small enough to attribute, and
                # must land somewhere the fix does not touch — that gap is what
                # makes the defect cross-file rather than local.
                if not (1 <= len(intro_files) <= 3):
                    continue
                elsewhere = {f for f in intro_files - fix_files if not is_test(f)}
                if not elsewhere:
                    continue
                intro_subject = run(["git", "log", "-1", "--pretty=format:%s", intro],
                                    cwd=repo_dir).strip()
                if NOT_A_REGRESSION.match(intro_subject):
                    continue
                found.append({
                    "fix_sha": sha, "fix_subject": subject,
                    "introducing_sha": intro, "introducing_subject": intro_subject,
                    "fix_files": sorted(fix_files),
                    "introducing_files": sorted(intro_files),
                    "cross_file_evidence": sorted(elsewhere),
                    "linked_issue": bool(ISSUE.search(subject)),
                    "is_revert": bool(REVERT.match(subject)),
                })
                if len(found) >= limit:
                    return found
                break  # one instance per fixed file, not one per blamed line
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repos", type=int, default=20)
    ap.add_argument("--per-repo", type=int, default=8)
    ap.add_argument("--out", default=str(Path(_ROOT) / "data" / "regressions.jsonl"))
    ap.add_argument("--workdir", default=str(Path(_ROOT) / ".mine-cache"))
    a = ap.parse_args()

    from experiments.benchmark import load_crossfile
    repos, seen = [], set()
    for t in load_crossfile(str(Path(_ROOT) / "data" / "crossfile.jsonl")):
        if t.repo not in seen:
            seen.add(t.repo); repos.append(t.repo)
        if len(repos) >= a.repos:
            break

    Path(a.workdir).mkdir(parents=True, exist_ok=True)
    out = Path(a.out)
    done = set()
    if out.is_file():
        done = {json.loads(l)["repo"] for l in out.read_text().splitlines() if l.strip()}

    funnel = {"repos": 0, "cloned": 0, "candidates": 0}
    with out.open("a") as handle:
        for index, repo in enumerate(repos, 1):
            funnel["repos"] += 1
            if repo in done:
                continue
            path = clone(repo, a.workdir)
            if path is None:
                print(f"  [{index}/{len(repos)}] {repo:<32} clone failed", flush=True)
                continue
            funnel["cloned"] += 1
            hits = mine(path, limit=a.per_repo)
            funnel["candidates"] += len(hits)
            for h in hits:
                handle.write(json.dumps({"repo": repo, **h}) + "\n")
            handle.flush()
            print(f"  [{index}/{len(repos)}] {repo:<32} {len(hits)} candidates "
                  f"(total {funnel['candidates']})", flush=True)
            shutil.rmtree(path, ignore_errors=True)

    print(f"\nfunnel: {json.dumps(funnel)}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
