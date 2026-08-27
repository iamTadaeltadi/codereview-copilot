#!/bin/bash
# Measure test coverage for the Django application (see .coveragerc for scope).
# Requires the full dependency set (use the built image or `bash scripts/test.sh`
# once to provision the virtualenv).
set -e

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
  .venv/bin/pip install --quiet -r requirements-dev.txt
fi
PYTHON_BIN=".venv/bin/python"

export DJANGO_SETTINGS_MODULE=django_backend.test_settings
export PYTHONPATH="$PWD/services/api:$PWD/services/agents:$PWD/services/graph${PYTHONPATH:+:$PYTHONPATH}"

if ! "${PYTHON_BIN}" -c "import coverage" >/dev/null 2>&1; then
  "${PYTHON_BIN}" -m pip install --quiet coverage==7.6.1
fi

echo "==> Django backend tests (coverage)"
"${PYTHON_BIN}" -m coverage run services/api/manage.py test core.tests

echo "==> Python integration tests (coverage, appended)"
"${PYTHON_BIN}" -m coverage run -a -m unittest discover -s tests -p 'test_*.py'

echo "==> Coverage report"
"${PYTHON_BIN}" -m coverage report
