#!/usr/bin/env python3
"""Condition E (paper/PREREG-E.md): raw CIS context for every c-CRAB task of run 4.

    .venv/bin/python experiments/cis_extract.py --cisd ~/Documents/cis-work/cis/target/release/cisd

For each task the source files our graph was built from in run 4 (graph.graph["sources"] of the
cached sparse graph) are written to a fresh directory, `cisd --mcp` indexes it, and for every
changed symbol the script asks CIS for its callers (get_callers), its own depth-1 neighbourhood
(expand_context) and the body of every hit (get_symbol_body). The raw hits are written before any
budget, with the seeds, CIS's index status and any error, and the directory is deleted.
Resumable: tasks already in the output are skipped.
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT, ROOT / "services" / "agents", ROOT / "services" / "graph"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from experiments.benchmark import load_ccrab  # noqa: E402

DATA = ROOT / "data" / "stage3_testgen_verified.jsonl"
ARCHIVE = ROOT / "data" / "testgen_combined.zip"
CACHE = ROOT / ".repo-cache"
SEED_KINDS = {"function", "class"}


def changed_ranges(diff):
    from experiments.run import changed_ranges as cr
    return cr(diff)


def tasks_of_run4(limit=400, max_diff_chars=40000):
    tasks = load_ccrab(str(DATA), testgen_archive=str(ARCHIVE), confirmed_only=True,
                       supported_source_only=True)
    tasks = [t for t in tasks if len(t.diff) <= max_diff_chars]
    return sorted(tasks, key=lambda t: t.task_id)[:limit]


def cached_sources(task):
    key = f"{task.repo.replace('/', '__')}@{task.review_commit[:12]}-sparse-h3-v2.pkl"
    path = CACHE / key
    if not path.is_file():
        return None, key
    with path.open("rb") as handle:
        graph = pickle.load(handle)
    return dict(graph.graph.get("sources") or {}), key


class Cisd:
    """One cisd --mcp process over line-delimited JSON-RPC on stdio."""

    def __init__(self, binary, repo_root, boot_timeout=900):
        env = dict(os.environ, CIS_REPO_ROOT=str(repo_root), CIS_FS_POLL_ONLY="1",
                   CIS_INDEX_RESPECT_GITIGNORE="0", CIS_SESSION_ID="0")
        self.proc = subprocess.Popen([str(binary), "--mcp"], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, bufsize=1, env=env, cwd=str(repo_root))
        self.out = queue.Queue()
        self.err_lines = []
        self.boot = None
        threading.Thread(target=self._read_out, daemon=True).start()
        threading.Thread(target=self._read_err, daemon=True).start()
        self.next_id = 0
        self.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                    "clientInfo": {"name": "ccrab-cis-extract", "version": "1"}})
        self.notify("notifications/initialized", {})
        start = time.time()
        while self.boot is None and time.time() - start < boot_timeout:
            if self.proc.poll() is not None:
                self.boot = f"exited {self.proc.returncode}"
                break
            time.sleep(0.2)
        self.boot_seconds = round(time.time() - start, 1)
        if self.boot is None:
            self.boot = "boot timeout"

    def _read_out(self):
        for line in self.proc.stdout:
            line = line.strip()
            if line.startswith("{"):
                try:
                    self.out.put(json.loads(line))
                except ValueError:
                    pass

    def _read_err(self):
        for line in self.proc.stderr:
            self.err_lines.append(line.rstrip())
            if "MCP boot complete" in line:
                self.boot = "ok"
            elif "MCP boot failed" in line:
                self.boot = line.strip()

    def notify(self, method, params):
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method, "params": params}) + "\n")
        self.proc.stdin.flush()

    def request(self, method, params, timeout=300):
        self.next_id += 1
        rid = self.next_id
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method,
                                          "params": params}) + "\n")
        self.proc.stdin.flush()
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msg = self.out.get(timeout=1)
            except queue.Empty:
                if self.proc.poll() is not None:
                    raise RuntimeError(f"cisd exited {self.proc.returncode}")
                continue
            if msg.get("id") == rid:
                if "error" in msg:
                    raise RuntimeError(json.dumps(msg["error"])[:300])
                return msg.get("result")
        raise RuntimeError(f"timeout on {method}")

    def call(self, tool, args):
        result = self.request("tools/call", {"name": tool, "arguments": args})
        if isinstance(result, dict):
            if result.get("isError"):
                text = "".join(c.get("text", "") for c in result.get("content") or [])
                raise RuntimeError(f"{tool}: {text[:300]}")
            if "structuredContent" in result:
                return result["structuredContent"]
            content = result.get("content") or []
            text = "".join(c.get("text", "") for c in content if c.get("type") == "text")
            try:
                return json.loads(text)
            except ValueError:
                return {"text": text}
        return result

    def close(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


def hits_of(resp):
    if isinstance(resp, dict):
        for key in ("hits", "matches", "results", "nodes"):
            if isinstance(resp.get(key), list):
                return resp[key]
    return resp if isinstance(resp, list) else []


def kind_of(hit):
    k = str(hit.get("kind") or hit.get("node_kind") or "").lower()
    return k


def kind_from_text(text):
    """class or function, from the symbol's own source (CIS hits carry no kind)."""
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("@"):
            continue
        if line.startswith("class "):
            return "class"
        if line.startswith(("def ", "async def ")):
            return "function"
        return "other"
    return None


def extract_task(cisd_bin, task, workroot):
    record = {"task_id": task.task_id, "seeds": [], "hits": [], "error": None,
              "index_status": None, "boot": None, "files": 0}
    sources, key = cached_sources(task)
    record["graph_cache"] = key
    if not sources:
        record["error"] = "no cached run-4 source files for this task"
        return record
    root = Path(tempfile.mkdtemp(prefix="cis-", dir=workroot))
    try:
        for rel, text in sources.items():
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text)
        record["files"] = len(sources)
        cis = None
        cis = Cisd(cisd_bin, root)
        record["boot"] = cis.boot
        record["boot_seconds"] = cis.boot_seconds
        try:
            if cis.boot != "ok":
                record["error"] = f"index failed: {cis.boot}; stderr tail: " + " | ".join(cis.err_lines[-5:])
                return record
            record["index_status"] = cis.call("index_status", {})
            ranges = changed_ranges(task.diff)
            seeds = []
            file_hubs = {}
            for path, spans in ranges.items():
                found = hits_of(cis.call("find_symbol", {"symbol": f"{path}::", "limit": 100000}))
                before = len(seeds)
                for h in found:
                    if h.get("file_path") != path or h.get("qualified_name") == path:
                        continue
                    kind = kind_of(h)
                    if not kind:
                        try:
                            body = cis.call("get_symbol_body", {"revision_id": h["revision_id_hex"],
                                                                "budget_tokens": 1000000})
                            kind = kind_from_text(body.get("body") or body.get("text") or "")
                        except (RuntimeError, KeyError):
                            kind = None
                        h["kind_inferred"] = kind
                    if kind not in SEED_KINDS:
                        continue
                    try:
                        lo, hi = int(h["start_line"]), int(h["end_line"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if any(lo <= last and hi >= first for first, last in spans):
                        seeds.append(dict(h, _lo=lo, _hi=hi))
                if len(seeds) == before:
                    # B's rule: a changed file with no function or class seed seeds its file node.
                    hubs = hits_of(cis.call("find_symbol", {"symbol": path, "prefer": "file", "limit": 50}))
                    hub = next((h for h in hubs if h.get("qualified_name") == path), None)
                    if hub:
                        file_hubs[path] = dict(hub, kind_inferred="file", _lo=0, _hi=0)
            # drop-class-seeds rule of run 4: a class whose own method is a seed is not seeded.
            # CIS returns no kind field; its Python names are path::Class.method, so a seed whose
            # qualified name prefixes another seed's (plus ".") is a class with a method seed.
            names = [s.get("qualified_name") or "" for s in seeds]
            seeds = [s for s in seeds
                     if not any(n.startswith((s.get("qualified_name") or "") + ".") for n in names)]
            seen = set()
            uniq = []
            for s in sorted(seeds, key=lambda s: (s["_lo"], s["_hi"] - s["_lo"])):
                if s.get("identity_id_hex") not in seen:
                    seen.add(s.get("identity_id_hex"))
                    uniq.append(s)
            uniq += list(file_hubs.values())
            record["seeds"] = [{k: v for k, v in s.items() if not k.startswith("_")} for s in uniq]
            bodies = {}
            for s in uniq:
                callers = hits_of(cis.call("get_callers", {"identity_id": s["identity_id_hex"],
                                                           "limit": 1000}))
                expand = hits_of(cis.call("expand_context", {"revision_id": s["revision_id_hex"],
                                                             "depth": 1, "limit": 1024}))
                for relation, group in (("caller", callers), ("expand", expand)):
                    for h in group:
                        rev = h.get("revision_id_hex") or h.get("revision_id")
                        text = None
                        if rev:
                            if rev not in bodies:
                                try:
                                    body = cis.call("get_symbol_body", {"revision_id": rev,
                                                                        "budget_tokens": 1000000})
                                    bodies[rev] = body
                                except RuntimeError as error:
                                    bodies[rev] = {"error": str(error)}
                            body = bodies[rev]
                            text = body.get("body") or body.get("text") or body.get("source")
                        record["hits"].append({
                            "seed": s.get("qualified_name"),
                            "relation": relation if relation == "caller" else (h.get("edge_type") or "expand"),
                            "group": relation,
                            "qualified_name": h.get("qualified_name"),
                            "kind": h.get("kind") or h.get("node_kind") or kind_from_text(text),
                            "path": h.get("file_path"),
                            "start_line": h.get("start_line"),
                            "end_line": h.get("end_line"),
                            "depth": h.get("depth"),
                            "identity_id": h.get("identity_id_hex"),
                            "revision_id": rev,
                            "text": text,
                        })
        finally:
            record["stderr_tail"] = cis.err_lines[-3:]
            cis.close()
    except Exception as error:  # recorded, never hidden
        record["error"] = f"{type(error).__name__}: {error}"
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cisd", required=True)
    ap.add_argument("--out", default=str(ROOT / "results" / "ccrab-cis" / "context-E-records.jsonl"))
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--only", default=None, help="comma-separated task ids")
    ap.add_argument("--workroot", default=None)
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.is_file():
        for line in out.read_text().splitlines():
            if line.strip():
                done.add(json.loads(line)["task_id"])
    tasks = tasks_of_run4(args.limit)
    if args.only:
        keep = set(args.only.split(","))
        tasks = [t for t in tasks if t.task_id in keep]
    workroot = args.workroot or tempfile.mkdtemp(prefix="cis-work-")
    print(f"tasks {len(tasks)}  already done {len(done & {t.task_id for t in tasks})}", flush=True)
    for i, task in enumerate(tasks, 1):
        if task.task_id in done:
            continue
        t0 = time.time()
        rec = extract_task(args.cisd, task, workroot)
        rec["seconds"] = round(time.time() - t0, 1)
        with out.open("a") as handle:
            handle.write(json.dumps(rec) + "\n")
        print(f"[{i}/{len(tasks)}] {task.task_id[:45]:<45} files={rec['files']:>3} "
              f"seeds={len(rec['seeds']):>3} hits={len(rec['hits']):>4} "
              f"{rec['seconds']:>6}s {('ERROR ' + rec['error'][:80]) if rec['error'] else ''}", flush=True)


if __name__ == "__main__":
    main()
