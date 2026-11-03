# News24 / 新浪财经 7×24

[![CI](https://github.com/1998x-stack/7x24/actions/workflows/ci.yml/badge.svg)](https://github.com/1998x-stack/7x24/actions/workflows/ci.yml)

A financial news collection research project. **V0.2 is an engineering-foundation release, not a production-grade news intelligence service.**

## Current capabilities (V0.2)

- Installable Python 3.11+ package with a stable `news24` command.
- Offline environment diagnostics and contract-fixture validation.
- Minimal one-page Sina feed HTTP client, with explicit source errors.
- A canonical, timezone-aware article contract, preserving source payloads.
- Canonical JSONL export and local inspection.
- Automated unit, contract, smoke, and legacy regression tests.
- A small, non-root Docker image (no Chromium required).

**Not implemented yet:** persistent ingestion checkpoints, historical backfill, SQLite storage, scheduling, AI job queue, live dashboard, guaranteed source availability. These are staged for V0.3 onward.

## Quick start

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
news24 doctor --json
news24 test-fixtures tests/fixtures/sina/feed_success.json
news24 collect --source sina --category A股 --limit 20 --output data/latest.jsonl
news24 inspect data/latest.jsonl --limit 5
```

Live collection depends on a third-party interface. Failure returns a nonzero exit code; an HTTP failure is **never** reported as an empty success. A 0-item valid response does not prove that data is available. The unversioned upstream API and pagination semantics need continuous verification.

To replace an existing export, explicitly pass `--force`. Exports are single-page snapshots, **not** a persistent store.

## Tests

```bash
make lint
make typecheck
make test
make smoke
```

The pre-refactor entrypoint `python -m src.main` and original scripts remain in place for comparison. They are **legacy** and do not inherit V0.2 reliability guarantees.

## Docker

```bash
docker build -t news24:0.2 .
docker run --rm -v "$PWD/data:/data" news24:0.2 doctor --json
docker compose run --rm news24 test-fixtures /app/tests/fixtures/sina/feed_success.json
```

The Compose profile runs a one-shot command; there is no scheduler daemon in V0.2. The image does not expose an API port.

## Architecture

- `src/news24/core/`: validated canonical domain data.
- `src/news24/sources/sina/`: feed parsing and single-page fetch.
- `src/news24/cli.py`: supported command-line entrypoint.
- `tests/fixtures/`: synthetic offline examples, not an API live-availability guarantee.
- `src/{collectors,processors,analyzers,storage,reporters}/`: prior experimental implementation, preserved for migration.

See [V0.2 runbook](docs/runbooks/v0.2.md), [architecture decision](docs/adr/0001-foundation.md), and [roadmap](docs/architecture/roadmap.md).

## Security and provenance

Keep secrets in environment variables, never in version control. Raw news and AI outputs are different data categories; V0.2 preserves the upstream record for future replay. Avoid rendering upstream HTML as trusted markup. Honor source terms, applicable rights and rate limits. No claim of regulatory compliance or investment accuracy is made.
