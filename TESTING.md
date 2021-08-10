# Testing

This repository includes runnable tests across the main application surfaces:

- Django API service: model, serializer, permission, auth, and API coverage
- agent runtime utilities: diff parsing, response parsing, graph tool wrapping, persistence
- repository graph retrieval coverage
- web client component coverage with Vitest and Testing Library

## Main command

Run the full suite from the repository root:

```bash
bash scripts/test.sh
```

## What it runs

1. Django tests with `services/api/django_backend/test_settings.py`
2. Python `unittest` suites in `tests/`
3. Web client component tests in `web/src/components/__tests__/`

## Coverage

Measure line coverage for the Django application:

```bash
bash scripts/coverage.sh
```

The scope is defined in `.coveragerc` (the `services/api/core` application
package). The suite keeps backend coverage above the configured
`fail_under = 80` threshold (currently ~86%). The agent and graph services ship
their own dependency manifests and are exercised by their own test modules.

## Notes

- The API test settings use SQLite so the suite does not require a local Postgres instance.
- The web tests run with Vitest and `jsdom`.
- The test runner prefers `.venv/bin/python` when available.
- If Vitest runs out of memory locally, `scripts/test.sh` sets `NODE_OPTIONS=--max-old-space-size=4096`.
- Standalone Python suites require `json_repair`; `scripts/test.sh` installs it automatically when missing.
- Agent runtime tests that need optional dependencies (GitPython, langchain) skip
  automatically when those packages are not installed in the active environment.
