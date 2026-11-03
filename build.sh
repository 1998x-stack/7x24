#!/usr/bin/env bash
# Deterministic setup of V0.2 engineering tools, without rewriting tracked files.
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m pip install -e '.[dev]'
"$PYTHON_BIN" -m news24 doctor --json
"$PYTHON_BIN" -m news24 test-fixtures tests/fixtures/sina/feed_success.json
"$PYTHON_BIN" -m pytest -q tests/unit tests/contract tests/test_system.py
echo "V0.2 foundation checks passed"
