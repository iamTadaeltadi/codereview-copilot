"""Check which generated defects the source repository's own test suite catches.

    python experiments/verify_by_tests.py --repos networkx/networkx tobymao/sqlglot

For each task: fetch the repository at the benchmark commit, install it into a
throwaway virtualenv, select the test files that mention the mutated function or
either module, run them once unmodified, apply only the real mutation (the
distractors are left out), run them again, and restore. A defect is
test-verified when at least one test passes before and fails after. Every
step's outcome is recorded, including "no tests selected" and "install failed",
so the funnel is visible. Results go to results/test-verified/verify.jsonl.
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "test-verified" / "verify.jsonl"
WORK = Path(os.environ.get("VERIFY_WORK", "/tmp/verify-by-tests"))
UV = shutil.which("uv") or str(Path.home() / ".local/bin/uv")
MAX_TEST_FILES = 40
TEST_TIMEOUT = 900


def sh(cmd, cwd, timeout=600, env=None, full=False):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    out = p.stdout + p.stderr
    return p.returncode, (out if full else out[-4000:])


def fetch(repo, commit):
    d = WORK / repo.replace("/", "__") / commit[:12]
    if (d / ".git").exists():
        return d
    d.mkdir(parents=True, exist_ok=True)
    for cmd in (["git", "init", "-q"], ["git", "remote", "add", "origin", f"https://github.com/{repo}.git"],
                ["git", "fetch", "-q", "--depth", "1", "origin", commit], ["git", "checkout", "-q", "FETCH_HEAD"]):
        for attempt in range(4):
            rc, out = sh(cmd, d, timeout=1200)
            if rc == 0:
                break
            time.sleep(20 * (attempt + 1))
        if rc:
            shutil.rmtree(d, ignore_errors=True)
            raise RuntimeError(f"fetch failed: {' '.join(cmd)}: {out[-300:]}")
    return d


def install(d):
    py = d / ".venv" / "bin" / "python"
    marker = d / ".venv" / ".installed"
    if marker.exists():
        return py
    if not py.exists():
        rc, out = sh([UV, "venv", "-q", "-p", "3.12", ".venv"], d)
        if rc:
            raise RuntimeError("venv: " + out[-300:])
    base = ["pytest", "pytest-timeout", "pytest-xdist", "pytest-mock"]
    attempts = (["-e", ".[all]"], ["-e", ".[complete]"], ["-e", ".[test]"], ["-e", ".[tests]"], ["-e", ".[dev]"], ["-e", "."])
    last = ""
    for extra in attempts:
        rc, out = sh([UV, "pip", "install", "-q", "-p", str(py), *extra, *base], d, timeout=1500)
        if rc == 0:
            marker.write_text(" ".join(extra))
            return py
        last = out
    raise RuntimeError("install failed: " + last[-400:])


def select_tests(d, task):
    fn = task["task_id"].split("::")[3]
    stems = {Path(task["defect_path"]).stem, Path(task["caller_path"]).stem} - {"__init__"}
    words = [fn] + sorted(stems)
    pattern = re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b")
    hits = []
    for p in d.rglob("test_*.py"):
        if ".venv" in p.parts or "site-packages" in p.parts:
            continue
        try:
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        score = len(pattern.findall(text))
        if score:
            hits.append((score, str(p.relative_to(d))))
    hits.sort(reverse=True)
    return [h[1] for h in hits[:MAX_TEST_FILES]], words


def run_tests(py, d, files):
    rc, out = sh([str(py), "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "-rA",
                  "-W", "ignore::pytest.PytestConfigWarning", "--continue-on-collection-errors", *files], d, timeout=TEST_TIMEOUT, full=True)
    passed = set(re.findall(r"^PASSED (\S+)", out, re.M))
    failed = set(re.findall(r"^(?:FAILED|ERROR) (\S+)", out, re.M))
    return passed, failed, out[-800:]


def mutate(d, task, forward=True):
    f = d / task["defect_path"]
    lines = f.read_text().split("\n")
    i = task["defect_line"] - 1
    src, dst = (task["before"], task["after"]) if forward else (task["after"], task["before"])
    if lines[i] != src:
        raise RuntimeError(f"line {task['defect_line']} is {lines[i]!r}, expected {src!r}")
    lines[i] = dst
    f.write_text("\n".join(lines))


def verify(task):
    rec = {"task_id": task["task_id"], "repo": task["repo"], "kind": task["kind"], "t": time.strftime("%F %T")}
    try:
        d = fetch(task["repo"], task["commit"])
        py = install(d)
        files, words = select_tests(d, task)
        rec.update(test_files=len(files), search_words=words)
        if not files:
            rec["status"] = "no tests selected"
            return rec
        before_pass, before_fail, tail = run_tests(py, d, files)
        rec.update(passed_before=len(before_pass), failed_before=len(before_fail))
        if not before_pass:
            rec["status"] = "no passing tests before mutation"
            rec["tail"] = tail
            return rec
        mutate(d, task, True)
        try:
            after_pass, after_fail, tail = run_tests(py, d, files)
        finally:
            mutate(d, task, False)
        flipped = sorted(before_pass & after_fail)
        rec.update(passed_after=len(after_pass), failed_after=len(after_fail), flipped=flipped[:20],
                   n_flipped=len(flipped), status="test-verified" if flipped else "not caught by selected tests")
        if flipped:
            rec["tail"] = tail[-600:]
    except subprocess.TimeoutExpired:
        rec["status"] = "timeout"
    except Exception as e:  # noqa: BLE001
        rec["status"] = "error: " + str(e)[:300]
    return rec


def main():
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", default=str(ROOT / "data" / "crossfile-v2.jsonl"))
    ap.add_argument("--repos", nargs="*", default=[])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--retry", nargs="*", default=[], help="status prefixes to redo, e.g. error timeout 'no passing'")
    ap.add_argument("--out", default=str(OUT), help="results file (default results/test-verified/verify.jsonl)")
    a = ap.parse_args()
    OUT = Path(a.out)
    tasks = [json.loads(l) for l in open(a.benchmark) if l.strip()]
    if a.repos:
        tasks = [t for t in tasks if t["repo"] in a.repos]
    done, keep = set(), []
    if OUT.exists():
        for line in OUT.open():
            if not line.strip():
                continue
            r = json.loads(line)
            if any(r["status"].startswith(p) for p in a.retry):
                continue
            done.add(r["task_id"]); keep.append(line)
        if a.retry:
            OUT.write_text("".join(keep))
    tasks = [t for t in tasks if t["task_id"] not in done]
    if a.limit:
        tasks = tasks[: a.limit]
    print(f"{len(tasks)} tasks to verify; work dir {WORK}", flush=True)
    with OUT.open("a") as out:
        for t in tasks:
            rec = verify(t)
            out.write(json.dumps(rec) + "\n"); out.flush()
            print(f"{rec['status']:<40}{t['repo']:<28}{t['kind']:<16}{rec.get('n_flipped','')}", flush=True)


if __name__ == "__main__":
    main()
