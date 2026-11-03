# Testing and release quality

## Required local sequence

1. Install Python 3.11+ with `python -m pip install -e '.[dev]'`.
2. Run `make lint typecheck test smoke`. These checks cover the supported News24 package and historical regression suite.
3. After any UI/API work, install `.[dev,browser]`, run `python -m playwright install chromium`, then `make browser`.
4. Build a wheel with `make build`; run `python scripts/verify_wheel.py dist` to confirm packaged resources and exclusion of archived legacy modules.

## Test boundaries

- `tests/unit`: pure parsing, models and CLI behavior
- `tests/contract`: Sina offline response shape and exact-quote golden examples
- `tests/integration`: SQLite migrations, transactional storage, worker, model fakes, review/web HTTP
- `tests/architecture`: module dependency direction, compatibility import identity, packaged resources
- `tests/e2e`: real Chromium local interactions with synthetic stored news
- `tests/legacy`: historical prototype regression; does not imply old runtime is production-ready

No network calls, paid model executions, or external stock-market predictions are required for CI. Source API live compatibility is a separate manual production gate. Pull requests must not mark offline test success as live contract verification.

## Data migrations

Migration scripts are immutable and additive; never edit an already released SQL migration. Add the next numeric file and update `SCHEMA_VERSION` in the canonical `infrastructure/sqlite/database.py`. Back up the SQLite WAL database consistently before applying upgrades. Add independent upgrade tests against prior schemas.
