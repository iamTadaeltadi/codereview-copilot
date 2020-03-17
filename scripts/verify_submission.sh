#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

echo "Checking repository submission readiness..."

if [ ! -d .git ]; then
  echo "FAIL: .git directory missing. Silver requires full git history in the upload zip."
  exit 1
fi

if find . -maxdepth 1 -name '*-upload.zip' | grep -q .; then
  echo "FAIL: submission artifact zip files found at repo root."
  exit 1
fi

empty_count=0
while read -r commit; do
  if [ -z "$(git ls-tree -r --name-only "${commit}")" ]; then
    git log -1 --format='  %h %s' "${commit}"
    empty_count=$((empty_count + 1))
  fi
done < <(git rev-list HEAD)

if [ "${empty_count}" -gt 0 ]; then
  echo "FAIL: ${empty_count} empty commit(s) in git history."
  exit 1
fi

if git ls-files | grep -qE '(^|/)node_modules/'; then
  echo "FAIL: node_modules is tracked in git."
  exit 1
fi

if git ls-files | grep -qE '__pycache__|\.pyc$'; then
  echo "FAIL: Python cache artifacts are tracked in git."
  exit 1
fi

if git ls-files | grep -qE '(^|/)(api/api|agents/agents|graph/graph|web/web|docs/docs|tests/tests|scripts/scripts|monitoring/monitoring)(/|$)'; then
  echo "FAIL: nested duplicate module directories are tracked in git."
  exit 1
fi

if [ ! -x scripts/test.sh ]; then
  chmod +x scripts/test.sh
fi

echo "Running full test suite..."
bash scripts/test.sh

echo "Repository checks passed."
