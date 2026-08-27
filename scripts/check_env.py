#!/usr/bin/env python3
"""Check that the environment is complete enough to boot and to run a review.

    python scripts/check_env.py            # reads .env, then the process env
    python scripts/check_env.py --strict   # also fail on placeholder values

Exit code 0 means the required set is present. Anything else is a failure a
human needs to read.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BOOT_REQUIRED = [
    "DJANGO_SECRET_KEY",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "REDIS_HOST",
    "GITHUB_CLIENT_ID",
    "GITHUB_CLIENT_SECRET",
    "GITHUB_WEBHOOK_SECRET",
]

REVIEW_REQUIRED = [
    "LANGGRAPH_API_URL",
    "LANGGRAPH_REVIEW_ASSISTANT_ID",
    "LANGGRAPH_FEEDBACK_ASSISTANT_ID",
    "LLM_MODEL_NAME",
]

PROVIDER_KEYS = [
    "CEREBRAS_API_KEY",
    "HYPERBOLIC_API_KEY",
    "OPENROUTER_API_KEY",
    "DEEPINFRA_API_TOKEN",
]

PLACEHOLDERS = {"change-me", "changeme", "your-key-here", "todo", "xxx"}


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    env = load_env_file(Path(args.env_file))
    env.update({k: v for k, v in os.environ.items() if v})

    missing_boot = [name for name in BOOT_REQUIRED if not env.get(name)]
    missing_review = [name for name in REVIEW_REQUIRED if not env.get(name)]
    has_provider = any(env.get(name) for name in PROVIDER_KEYS)

    placeholders = [
        name
        for name, value in env.items()
        if value.lower() in PLACEHOLDERS
    ]

    if missing_boot:
        print("MISSING — the API will not work without these:")
        for name in missing_boot:
            print(f"  - {name}")

    if missing_review:
        print("MISSING — the API boots, but every review will fail:")
        for name in missing_review:
            print(f"  - {name}")

    if not has_provider:
        print("MISSING — no LLM provider key is set. One of:")
        for name in PROVIDER_KEYS:
            print(f"  - {name}")

    if placeholders:
        label = "PLACEHOLDER" if args.strict else "PLACEHOLDER (warning)"
        print(f"{label} — still set to a template value:")
        for name in sorted(placeholders):
            print(f"  - {name}")

    failed = bool(missing_boot or missing_review or not has_provider)
    if args.strict and placeholders:
        failed = True

    if failed:
        print(f"\ncheck_env: FAILED (read {args.env_file})")
        return 1

    print(f"check_env: OK (read {args.env_file})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
