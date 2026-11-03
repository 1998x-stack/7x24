.PHONY: install lint typecheck test smoke build

PYTHON ?= python3

install:
	$(PYTHON) -m pip install -e '.[dev]'

lint:
	$(PYTHON) -m ruff check src/news24 tests/unit/test_news24.py tests/contract/test_sina_feed.py

typecheck:
	$(PYTHON) -m mypy src/news24

test:
	$(PYTHON) -m pytest -q tests/unit tests/contract tests/test_system.py

smoke:
	$(PYTHON) -m news24 doctor --json
	$(PYTHON) -m news24 test-fixtures tests/fixtures/sina/feed_success.json

build:
	$(PYTHON) -m pip wheel --no-deps --wheel-dir dist .
