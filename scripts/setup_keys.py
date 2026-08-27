#!/usr/bin/env python3
"""Paste two API keys, get a working .env.

    python scripts/setup_keys.py

Writes CEREBRAS_API_KEY and OPENROUTER_API_KEY into .env (creating it from
.env.example if needed), fills in the base URLs, and calls each provider once
to prove the key actually works before you rely on it in a run.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
EXAMPLE = ROOT / ".env.example"

PROVIDERS = {
    "CEREBRAS": {
        "url": "https://cloud.cerebras.ai",
        "base": "https://api.cerebras.ai/v1",
        "note": "free tier, no card needed",
        "probe": "https://api.cerebras.ai/v1/models",
    },
    "OPENROUTER": {
        "url": "https://openrouter.ai/settings/keys",
        "base": "https://openrouter.ai/api/v1",
        "note": "needs about $10 of credit",
        "probe": "https://openrouter.ai/api/v1/models",
    },
}


def read_env() -> dict:
    values = {}
    source = ENV if ENV.is_file() else EXAMPLE
    if not source.is_file():
        return values
    for line in source.read_text().splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, _, value = stripped.partition("=")
            values[key.strip()] = value.strip()
    return values


def write_env(values: dict) -> None:
    lines = []
    source = ENV if ENV.is_file() else EXAMPLE
    seen = set()
    if source.is_file():
        for line in source.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in values:
                    lines.append(f"{key}={values[key]}")
                    seen.add(key)
                    continue
            lines.append(line)
    for key, value in values.items():
        if key not in seen:
            lines.append(f"{key}={value}")
    ENV.write_text("\n".join(lines) + "\n")


def probe(name: str, key: str) -> tuple[bool, str]:
    spec = PROVIDERS[name]
    request = urllib.request.Request(
        spec["probe"], headers={"Authorization": f"Bearer {key}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
            count = len(payload.get("data") or [])
            return True, f"key works, {count} models visible"
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            return False, f"key rejected (HTTP {error.code})"
        return False, f"HTTP {error.code}"
    except Exception as error:
        return False, f"could not reach the provider: {error}"


def main() -> int:
    print("Two keys. Open each link, create a key, paste it here.")
    print("Press Enter to skip one and keep whatever is already in .env.\n")

    values = read_env()
    results = {}

    for name, spec in PROVIDERS.items():
        existing = values.get(f"{name}_API_KEY", "")
        status = "already set" if existing else "not set"
        print(f"{name}  ({spec['note']}) — currently {status}")
        print(f"  {spec['url']}")
        entered = input(f"  paste {name}_API_KEY: ").strip()
        key = entered or existing
        if not key:
            print("  skipped\n")
            continue
        values[f"{name}_API_KEY"] = key
        values[f"{name}_API_BASE_URL"] = spec["base"]
        ok, message = probe(name, key)
        results[name] = ok
        print(f"  {'OK' if ok else 'FAILED'}: {message}\n")

    write_env(values)
    print(f"wrote {ENV}")

    working = [name for name, ok in results.items() if ok]
    if not working:
        print("\nNo working key yet. The experiment cannot run until at least one works.")
        return 1
    if len(working) == 1:
        print(f"\n{working[0]} works. One model family only — the run costs $19.77")
        print("instead of $25.63, and the paper loses its multi-model defence.")
    else:
        print("\nBoth providers work. The full two-model matrix is available.")
    print("\nNext: python scripts/check_env.py")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\ncancelled")
        sys.exit(130)
