#!/usr/bin/env bash
# V0.3 deterministic build/test gate. Does not mutate tracked files.
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m pip install -e '.[dev]'
"$PYTHON_BIN" -m ruff check src/news24 tests/unit tests/contract tests/integration
"$PYTHON_BIN" -m mypy src/news24
"$PYTHON_BIN" -m pytest -q tests/unit tests/contract tests/integration tests/test_system.py
"$PYTHON_BIN" -m news24 doctor --json
"$PYTHON_BIN" -m news24 test-fixtures tests/fixtures/sina/feed_success.json
echo "V0.3 foundation checks passed"
