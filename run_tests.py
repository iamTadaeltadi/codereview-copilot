#!/usr/bin/env python3
"""Run the repository test suites from the project root."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


ROOT = os.path.dirname(os.path.abspath(__file__))


def _python_bin() -> str:
    venv_python = os.path.join(ROOT, ".venv", "bin", "python")
    if os.path.isfile(venv_python):
        return venv_python
    return sys.executable


def _run(command: list[str]) -> int:
    env = os.environ.copy()
    env.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.test_settings")
    env["PYTHONPATH"] = os.pathsep.join(
        [
            os.path.join(ROOT, "services", "api"),
            os.path.join(ROOT, "services", "agents"),
            os.path.join(ROOT, "services", "graph"),
            env.get("PYTHONPATH", ""),
        ]
    ).strip(os.pathsep)
    result = subprocess.run(command, cwd=ROOT, env=env)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repository test suites")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--suite",
        "-s",
        choices=("all", "backend", "python", "frontend"),
        default="all",
        help="Run a specific suite",
    )
    args = parser.parse_args()
    python = _python_bin()
    verbose_flag = ["-v", "2"] if args.verbose else []

    if args.suite in {"all", "backend"}:
        code = _run([python, "services/api/manage.py", "test", "core.tests", *verbose_flag])
        if code != 0:
            return code

    if args.suite in {"all", "python"}:
        code = _run(
            [
                python,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_*.py",
                *(["-v"] if args.verbose else []),
            ]
        )
        if code != 0:
            return code

    if args.suite in {"all", "frontend"}:
        code = subprocess.run(["npm", "test"], cwd=os.path.join(ROOT, "web")).returncode
        if code != 0:
            return code

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
