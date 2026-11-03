#!/usr/bin/env bash
# V1.1 architecture-compatible build/test gate. Does not mutate tracked files.
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m pip install -e '.[dev]'
"$PYTHON_BIN" -m ruff check src/news24 tests/unit tests/contract tests/integration tests/architecture
"$PYTHON_BIN" -m mypy src/news24
"$PYTHON_BIN" -m pytest -q tests/unit tests/contract tests/integration tests/architecture tests/legacy/test_system.py
"$PYTHON_BIN" -m news24 doctor --json
"$PYTHON_BIN" -m news24 test-fixtures tests/fixtures/sina/feed_success.json
"$PYTHON_BIN" -m pip wheel --no-deps --wheel-dir dist .
"$PYTHON_BIN" scripts/verify_wheel.py dist
echo "V1.1 architecture checks passed"
