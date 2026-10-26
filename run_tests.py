#!/usr/bin/env python3
"""Run the repository test suites from the project root.

    python run_tests.py                 # backend, python and frontend suites
    python run_tests.py --suite python  # one suite
    PYTHON=.venv/bin/python python run_tests.py

Suites: backend = Django tests for services/api (SQLite settings, no Postgres
needed); python = unittest discovery over tests/ (experiments, graph, agent
runtime); frontend = Vitest in web/ (skipped with a message when node_modules
is missing).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SUITES = ("backend", "python", "frontend")


def _python_bin() -> str:
    override = os.environ.get("PYTHON")
    if override:
        return override
    venv_python = os.path.join(ROOT, ".venv", "bin", "python")
    return venv_python if os.path.isfile(venv_python) else sys.executable


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.test_settings")
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (
            ROOT,
            os.path.join(ROOT, "services", "api"),
            os.path.join(ROOT, "services", "agents"),
            os.path.join(ROOT, "services", "graph"),
            env.get("PYTHONPATH", ""),
        ) if p
    )
    return env


def _run(name: str, command: list[str], cwd: str = ROOT) -> int:
    print(f"== {name}: {' '.join(command)}", flush=True)
    return subprocess.run(command, cwd=cwd, env=_env()).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repository test suites")
    parser.add_argument("--verbose", "-v", action="store_true", help="verbose output")
    parser.add_argument("--suite", "-s", choices=("all", *SUITES), default="all", help="run one suite")
    args = parser.parse_args()
    python = _python_bin()
    wanted = SUITES if args.suite == "all" else (args.suite,)

    for suite in wanted:
        if suite == "backend":
            code = _run("backend", [python, "services/api/manage.py", "test", "core.tests", *(["-v", "2"] if args.verbose else [])])
        elif suite == "python":
            code = _run("python", [python, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", *(["-v"] if args.verbose else [])])
        else:
            web = os.path.join(ROOT, "web")
            if shutil.which("npm") is None or not os.path.isdir(os.path.join(web, "node_modules")):
                print("== frontend: skipped (run `npm ci` in web/ first)", flush=True)
                continue
            code = _run("frontend", ["npm", "test", "--", "--run"], cwd=web)
        if code != 0:
            print(f"== {suite}: FAILED ({code})", flush=True)
            return code
    print("== all requested suites passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
