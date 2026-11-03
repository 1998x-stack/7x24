.PHONY: install lint typecheck test smoke build

PYTHON ?= python3

install:
	$(PYTHON) -m pip install -e '.[dev]'

lint:
	$(PYTHON) -m ruff check src/news24 tests/unit tests/contract tests/integration

typecheck:
	$(PYTHON) -m mypy src/news24

test:
	$(PYTHON) -m pytest -q tests/unit tests/contract tests/integration tests/test_system.py

smoke:
	$(PYTHON) -m news24 doctor --json
	$(PYTHON) -m news24 test-fixtures tests/fixtures/sina/feed_success.json
	$(PYTHON) -m news24 db migrate --db /tmp/news24-smoke.sqlite3
	$(PYTHON) -m news24 db stats --db /tmp/news24-smoke.sqlite3
	$(PYTHON) -m news24 jobs status --db /tmp/news24-smoke.sqlite3
	$(PYTHON) -m news24 report daily --date 2026-11-02 --db /tmp/news24-smoke.sqlite3
	$(PYTHON) -m news24 intelligence events --db /tmp/news24-smoke.sqlite3

build:
	$(PYTHON) -m pip wheel --no-deps --wheel-dir dist .
