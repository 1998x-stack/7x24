.PHONY: install lint typecheck test browser smoke build wheelcheck

PYTHON ?= python3

install:
	$(PYTHON) -m pip install -e '.[dev]'

lint:
	$(PYTHON) -m ruff check src/news24 tests/unit tests/contract tests/integration tests/architecture

typecheck:
	$(PYTHON) -m mypy src/news24

test:
	$(PYTHON) -m pytest -q tests/unit tests/contract tests/integration tests/architecture tests/legacy/test_system.py

browser:
	$(PYTHON) -m pytest -q tests/e2e

smoke:
	$(PYTHON) -m news24 doctor --json
	$(PYTHON) -m news24 test-fixtures tests/fixtures/sina/feed_success.json
	$(PYTHON) -m news24 db migrate --db /tmp/news24-smoke.sqlite3
	$(PYTHON) -m news24 audit --db /tmp/news24-smoke.sqlite3
	$(PYTHON) -m news24 evaluate evidence \
	  --dataset tests/fixtures/intelligence/evidence_gold.json \
	  --db /tmp/news24-smoke.sqlite3

build:
	$(PYTHON) -m pip wheel --no-deps --wheel-dir dist .

wheelcheck: build
	$(PYTHON) scripts/verify_wheel.py dist
