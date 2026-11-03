# News24 — 新浪财经 7×24 新闻采集与研究平台

[![CI](https://github.com/1998x-stack/7x24/actions/workflows/ci.yml/badge.svg)](https://github.com/1998x-stack/7x24/actions/workflows/ci.yml)

News24 V0.3 introduces a replayable, transactional SQLite ingestion backend for Sina 7×24. **It is an experimental research system, not a validated financial market data service.**

## Implemented in V0.3

- Durable SQLite / WAL database, migration v1, per-source/per-category checkpoints.
- Async HTTPX page retrieval, bounded retries and delays, JSON/JSONP validation.
- Raw page snapshots, canonical articles, multi-category associations, article revisions.
- Idempotent article UPSERT by `(source, source_id)`; no overwriting history on updates.
- Checkpoint is advanced in the *same transaction* as news writes **only when coverage is complete**.
- SQLite FTS5 trigram search with short-query LIKE fallback.
- Incremental ingestion, date-window backfill, local recovery of interrupted runs, diagnostics.
- Offline unit/contract/integration tests and deliberately injected failures.

### Quick start

Requires Python 3.11+ with SQLite FTS5 trigram support.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

news24 doctor --json
news24 test-fixtures tests/fixtures/sina/feed_success.json

news24 db migrate --db data/news24.sqlite3
news24 ingest --source sina --category all --max-pages 50 --db data/news24.sqlite3
news24 db stats --db data/news24.sqlite3
news24 db recent --limit 10 --db data/news24.sqlite3
news24 db search "经济数据" --db data/news24.sqlite3
news24 db revisions sina_7x24:4700001 --db data/news24.sqlite3
```

**Backfill with explicit time-zone offsets:**

```bash
news24 backfill --start 2026-03-01T00:00:00+08:00 \
  --end 2026-03-03T00:00:00+08:00 \
  --max-pages 100 --db data/news24.sqlite3
```

A max-page cutoff without an observed end/boundary prints `INCOMPLETE` and exits with code **3**: saved records are inspectable, but the checkpoint is not advanced. Re-run with a larger page limit. Backfill does not change the real-time cursor, even on success.

The upstream API is **unofficial/unversioned**. The page-walker assumes descending numeric source IDs and a stable page listing during traversal, checking for misordered or overlapping pages. Live behavior is not guaranteed; mutations of older stories that fall outside the overlap window may require replay/backfill. Large feed histories can exceed memory limits: bounded, streaming backfills are a future improvement. Respect rate limits, terms and content rights.

### Tests

```bash
make lint typecheck test smoke
```

A legacy standalone `sina7x24_playwright.py` and `python -m src.main` remain unchanged for comparison; new persistence guarantees do **not** extend to those entrypoints.

### Docker

```bash
docker build -t news24:0.3 .
docker run --rm news24:0.3 doctor --json
docker volume create news24-data
docker run --rm -v news24-data:/data news24:0.3 db migrate
docker run --rm -v news24-data:/data news24:0.3 ingest --max-pages 50
docker run --rm -v news24-data:/data news24:0.3 db stats
```

No scheduler, model analysis, realtime API or Web UI in V0.3. For roadmap and operational limits see [V0.3 runbook](docs/runbooks/v0.3.md) and [ADR 0002](docs/adr/0002-transactional-ingestion.md).

Data is not investment advice. Source content and model predictions must not be treated as verified price signals.
