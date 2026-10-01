#!/usr/bin/env python3
"""Regenerate the cross-file benchmark from cached sources, with verification.

    python experiments/rebuild_crossfile.py --out data/crossfile-v2.jsonl

The first benchmark is withdrawn: its distractors broke the file in 145 of 204
tasks and its evidence was a regex coincidence in two-thirds of them. This
rebuilds from the same repositories at the same commits, using the files the
first run already fetched, with evidence verified on the caller's syntax tree
and every distractor parse-checked. No network is needed.

The funnel is printed, not hidden.
"""
from __future__ import annotations

import argparse, collections, json, os, sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "services", "graph")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from experiments.benchmark import load_crossfile
from experiments.crossfile import build_diff, find_defects
from experiments.evidence import sources_for


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default=str(Path(_ROOT) / "data" / "crossfile.jsonl"))
    ap.add_argument("--out", default=str(Path(_ROOT) / "data" / "crossfile-v2.jsonl"))
    ap.add_argument("--per-repo", type=int, default=12)
    a = ap.parse_args()

    old = load_crossfile(a.source)
    pools = collections.defaultdict(dict)
    for t in old:
        try:
            pools[(t.repo, t.head_commit)].update(sources_for(t))
        except Exception:
            pass
    funnel = {"pools": len(pools), "files": sum(len(v) for v in pools.values()),
              "defects": 0, "by_kind": collections.Counter(), "repos_with_defects": 0}
    with open(a.out, "w") as h:
        for (repo, commit), sources in sorted(pools.items()):
            defects = find_defects(sources, max_per_repo=a.per_repo)
            if defects:
                funnel["repos_with_defects"] += 1
            for d in defects:
                diff = build_diff(d)
                funnel["defects"] += 1
                funnel["by_kind"][d.kind] += 1
                h.write(json.dumps({
                    "task_id": f"xf::{repo.replace('/', '__')}::{d.defect_id}",
                    "repo": repo, "commit": commit, "kind": d.kind,
                    "defect_path": d.definition_path, "defect_line": d.definition_line,
                    "caller_path": d.caller_path, "caller_line": d.caller_line,
                    "before": d.before, "after": d.after, "why": d.why,
                    "evidence": d.evidence, "argument": d.argument,
                    "distractor_lines": [c.line for c in d.distractors],
                    "verified": "ast", "diff": diff,
                }) + "\n")
            print(f"  {repo:<34} {len(sources):>3} files  {len(defects):>2} defects", flush=True)
    print(f"\nfunnel: pools={funnel['pools']} files={funnel['files']} "
          f"repos_with_defects={funnel['repos_with_defects']} defects={funnel['defects']}")
    for k, n in funnel["by_kind"].most_common():
        print(f"  {k:<16} {n}")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__" and "--clone" not in sys.argv and "--trees" not in sys.argv:
    raise SystemExit(main())


# --- whole-repository mode -------------------------------------------------
# Two cached files per task make a thin pool, and import resolution needs the
# real package layout. This clones each repository at depth one, generates from
# up to a few hundred production files, and writes the definition and caller
# files into the source cache so that every later run is offline.

import hashlib, random, shutil, subprocess

SKIP_DIR = {"tests", "test", "testing", "docs", "doc", "examples", "example", "benchmarks",
            "scripts", "tools", "build", "dist", ".git", "node_modules", "vendor", "third_party"}


def _clone(repo, workdir):
    target = Path(workdir) / repo.replace("/", "__")
    if (target / ".git").is_dir():
        return target
    subprocess.run(["git", "clone", "--depth", "1", "--quiet", f"https://github.com/{repo}.git", str(target)],
                   capture_output=True, text=True, timeout=1200)
    return target if (target / ".git").is_dir() else None


def _head(repo_dir):
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True,
                          text=True).stdout.strip()


def _production_files(repo_dir, cap, seed):
    files = []
    for p in Path(repo_dir).rglob("*.py"):
        rel = p.relative_to(repo_dir)
        parts = set(rel.parts[:-1])
        if parts & SKIP_DIR or rel.name.startswith("test_") or rel.name in {"setup.py", "conftest.py"}:
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if 800 < size < 200_000:
            files.append((str(rel), size))
    rng = random.Random(seed)
    rng.shuffle(files)
    out = {}
    for rel, _ in files[:cap]:
        try:
            out[rel] = (Path(repo_dir) / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    return out


def _cache_sources(repo, commit, defect_path, caller_path, sources, cache_dir=".source-cache"):
    wanted = [p for p in (defect_path, caller_path) if p]
    key = hashlib.sha1(f"{repo}@{commit}::{'|'.join(wanted)}".encode()).hexdigest()
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    (Path(cache_dir) / f"{key}.json").write_text(json.dumps({p: sources[p] for p in wanted}))


def rebuild_from_clones(repos, out_path, workdir, per_repo=8, cap=300, seed=7):
    funnel = {"repos": 0, "cloned": 0, "defects": 0, "by_kind": collections.Counter()}
    done = set()
    if Path(out_path).is_file():
        done = {json.loads(l)["repo"] for l in open(out_path) if l.strip()}
    with open(out_path, "a") as h:
        for i, repo in enumerate(repos, 1):
            funnel["repos"] += 1
            if repo in done:
                continue
            repo_dir = _clone(repo, workdir)
            if repo_dir is None:
                print(f"  [{i}/{len(repos)}] {repo:<34} clone failed", flush=True)
                continue
            funnel["cloned"] += 1
            commit = _head(repo_dir)
            sources = _production_files(repo_dir, cap, seed)
            defects = find_defects(sources, max_per_repo=per_repo)
            for d in defects:
                _cache_sources(repo, commit, d.definition_path, d.caller_path, sources)
                funnel["defects"] += 1
                funnel["by_kind"][d.kind] += 1
                h.write(json.dumps({
                    "task_id": f"xf::{repo.replace('/', '__')}::{d.defect_id}",
                    "repo": repo, "commit": commit, "kind": d.kind,
                    "defect_path": d.definition_path, "defect_line": d.definition_line,
                    "caller_path": d.caller_path, "caller_line": d.caller_line,
                    "before": d.before, "after": d.after, "why": d.why,
                    "evidence": d.evidence, "argument": d.argument,
                    "distractor_lines": [c.line for c in d.distractors],
                    "verified": "ast", "diff": build_diff(d),
                }) + "\n")
            h.flush()
            print(f"  [{i}/{len(repos)}] {repo:<34} {len(sources):>3} files  {len(defects):>2} defects "
                  f"(total {funnel['defects']})", flush=True)
            shutil.rmtree(repo_dir, ignore_errors=True)
    print(f"\nfunnel: {json.dumps({k: (dict(v) if isinstance(v, collections.Counter) else v) for k, v in funnel.items()})}")


if __name__ == "__main__" and "--clone" in sys.argv:
    import argparse as _ap
    ap = _ap.ArgumentParser(); ap.add_argument("--clone", action="store_true")
    ap.add_argument("--out", default=str(Path(_ROOT) / "data" / "crossfile-v2.jsonl"))
    ap.add_argument("--per-repo", type=int, default=8); ap.add_argument("--cap", type=int, default=300)
    ap.add_argument("--workdir", default=str(Path(_ROOT) / ".clone-cache"))
    ap.add_argument("--reverse", action="store_true")
    a = ap.parse_args()
    repos = sorted({t.repo for t in load_crossfile(str(Path(_ROOT) / "data" / "crossfile.jsonl"))})
    if a.reverse:
        repos = repos[::-1]
    Path(a.workdir).mkdir(parents=True, exist_ok=True)
    rebuild_from_clones(repos, a.out, a.workdir, per_repo=a.per_repo, cap=a.cap)
    raise SystemExit(0)


# --- tree-listing mode -----------------------------------------------------
# A depth-one clone of a large repository is hundreds of megabytes, and on a
# slow link that is a quarter of an hour per repository. The commit is read
# with ls-remote, which costs no API call; one tree listing names every file;
# and the Python files are fetched individually from raw.githubusercontent,
# which has no rate limit, in parallel.

import urllib.request
from concurrent.futures import ThreadPoolExecutor


def _ls_remote_head(repo):
    out = subprocess.run(["git", "ls-remote", f"https://github.com/{repo}.git", "HEAD"],
                         capture_output=True, text=True, timeout=120).stdout
    return out.split()[0] if out.strip() else None


def _tree(repo, sha):
    url = f"https://api.github.com/repos/{repo}/git/trees/{sha}?recursive=1"
    req = urllib.request.Request(url, headers={"User-Agent": "codereview-copilot-experiments",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def _pick_from_tree(tree, cap, seed):
    """Whole directories, largest first, until the cap.

    A random sample of three hundred files from a sprawling repository rarely
    holds both a definition and its caller, and import resolution then finds
    nothing: airflow and home-assistant yielded zero defects from 300 files
    each. Files that import each other live near each other, so the pool is
    built from complete directories in descending size, which keeps callers
    and callees together. The first fifteen repositories were sampled at
    random before this change; the data README records which.
    """
    by_dir = collections.defaultdict(list)
    for entry in tree.get("tree", []):
        path = entry.get("path", "")
        if entry.get("type") != "blob" or not path.endswith(".py"):
            continue
        parts = path.split("/"); name = parts[-1]; dirs = set(parts[:-1])
        if dirs & SKIP_DIR or name.startswith("test_") or name in {"setup.py", "conftest.py"}:
            continue
        size = entry.get("size") or 0
        if 800 < size < 200_000:
            by_dir["/".join(parts[:-1])].append(path)
    out = []
    for d in sorted(by_dir, key=lambda d: (-len(by_dir[d]), d)):
        for path in sorted(by_dir[d]):
            if len(out) >= cap:
                return out
            out.append(path)
    return out


POOL_DIR = Path(_ROOT) / ".pool-cache"


def _save_pool(repo, sha, sources):
    """Keep the whole pool: the safe-twin generator needs every caller, not
    just the one that demonstrated the dependency."""
    POOL_DIR.mkdir(parents=True, exist_ok=True)
    (POOL_DIR / f"{repo.replace('/', '__')}@{sha}.json").write_text(json.dumps(sources))


def load_pool(repo, sha):
    f = POOL_DIR / f"{repo.replace('/', '__')}@{sha}.json"
    return json.loads(f.read_text()) if f.is_file() else None


def refetch_pools(out_path, cap=300, seed=7, workers=12):
    """Re-fetch pools for repositories already in the output whose pool was
    not kept, at the commit their tasks record, so twins match the tasks."""
    from experiments.sparse import fetch_file
    seen = {}
    for l in open(out_path):
        if l.strip():
            r = json.loads(l); seen[r["repo"]] = r["commit"]
    for i, (repo, sha) in enumerate(sorted(seen.items()), 1):
        if load_pool(repo, sha) is not None:
            continue
        try:
            tree = _tree(repo, sha)
        except Exception as e:
            print(f"  [{i}] {repo:<34} listing failed: {e}", flush=True); continue
        paths = _pick_from_tree(tree, cap, seed)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            texts = list(pool.map(lambda p: fetch_file(repo, sha, p), paths))
        sources = {p: t for p, t in zip(paths, texts) if t}
        _save_pool(repo, sha, sources)
        print(f"  [{i}] {repo:<34} pool {len(sources)} files", flush=True)


def rebuild_from_trees(repos, out_path, per_repo=8, cap=300, seed=7, workers=12):
    from experiments.sparse import fetch_file
    funnel = {"repos": 0, "listed": 0, "defects": 0, "by_kind": collections.Counter()}
    done = set()
    if Path(out_path).is_file():
        done = {json.loads(l)["repo"] for l in open(out_path) if l.strip()}
    with open(out_path, "a") as h:
        for i, repo in enumerate(repos, 1):
            funnel["repos"] += 1
            if repo in done:
                continue
            try:
                sha = _ls_remote_head(repo)
                tree = _tree(repo, sha) if sha else None
            except Exception as e:
                print(f"  [{i}/{len(repos)}] {repo:<34} listing failed: {e}", flush=True); continue
            if not tree:
                continue
            funnel["listed"] += 1
            paths = _pick_from_tree(tree, cap, seed)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                texts = list(pool.map(lambda p: fetch_file(repo, sha, p), paths))
            sources = {p: t for p, t in zip(paths, texts) if t}
            _save_pool(repo, sha, sources)
            defects = find_defects(sources, max_per_repo=per_repo)
            for d in defects:
                _cache_sources(repo, sha, d.definition_path, d.caller_path, sources)
                funnel["defects"] += 1; funnel["by_kind"][d.kind] += 1
                h.write(json.dumps({
                    "task_id": f"xf::{repo.replace('/', '__')}::{d.defect_id}",
                    "repo": repo, "commit": sha, "kind": d.kind,
                    "defect_path": d.definition_path, "defect_line": d.definition_line,
                    "caller_path": d.caller_path, "caller_line": d.caller_line,
                    "before": d.before, "after": d.after, "why": d.why,
                    "evidence": d.evidence, "argument": d.argument,
                    "distractor_lines": [c.line for c in d.distractors],
                    "verified": "ast", "diff": build_diff(d),
                }) + "\n")
            h.flush()
            print(f"  [{i}/{len(repos)}] {repo:<34} {len(sources):>3}/{len(paths):<3} files  "
                  f"{len(defects):>2} defects (total {funnel['defects']})", flush=True)
    print(f"\nfunnel: {json.dumps({k: (dict(v) if isinstance(v, collections.Counter) else v) for k, v in funnel.items()})}")


if __name__ == "__main__" and "--trees" in sys.argv:
    import argparse as _ap
    ap = _ap.ArgumentParser(); ap.add_argument("--trees", action="store_true")
    ap.add_argument("--out", default=str(Path(_ROOT) / "data" / "crossfile-v2.jsonl"))
    ap.add_argument("--per-repo", type=int, default=8); ap.add_argument("--cap", type=int, default=300)
    ap.add_argument("--workers", type=int, default=12); ap.add_argument("--pools-only", action="store_true")
    a = ap.parse_args()
    ap2 = _ap.ArgumentParser(); ap2.add_argument("--pools-only", action="store_true")
    repos = sorted({t.repo for t in load_crossfile(str(Path(_ROOT) / "data" / "crossfile.jsonl"))})
    if "--pools-only" in sys.argv:
        refetch_pools(a.out, cap=a.cap, workers=a.workers)
    else:
        rebuild_from_trees(repos, a.out, per_repo=a.per_repo, cap=a.cap, workers=a.workers)
    raise SystemExit(0)
