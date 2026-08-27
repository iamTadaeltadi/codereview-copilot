#!/bin/bash
set -e

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
  .venv/bin/pip install --quiet -r requirements-dev.txt
fi
PYTHON_BIN=".venv/bin/python"

export DJANGO_SETTINGS_MODULE=django_backend.test_settings
export PYTHONPATH="$PWD/services/api:$PWD/services/agents:$PWD/services/graph${PYTHONPATH:+:$PYTHONPATH}"

echo "==> Django backend tests"
"${PYTHON_BIN}" services/api/manage.py test core.tests -v 2

echo "==> Python integration tests"
"${PYTHON_BIN}" -m unittest discover -s tests -p 'test_*.py' -v

echo "==> Frontend tests"
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=4096}"
cd web
if [ ! -d node_modules ]; then
  npm ci
fi
npm test

echo "All test suites passed."
