# News24 staged refactor

## V0.2 Foundation (this PR)

Packaging, CLI, response contract, offline fixtures, explicit source errors, Docker, CI, legacy preservation.

## V0.3 Lossless ingestion

- Async reusable HTTP transport; validated cursor semantics and multi-page coverage.
- SQLite/WAL migration with `news`, `news_revisions`, `source_snapshots`, `source_checkpoints`, `ingestion_runs`.
- Atomic transaction for raw snapshots, article upserts, revisions, and watermark advancement.
- Idempotency using `(source, source_id)`; tombstones and corrections.
- Golden regression comparing original sample fields to normalized records.
- Live Sina access checks, respect source usage and rate limits.

## V0.4 Jobs and resilience

Independent collection, analysis, reporting; persistent job queue; recovery, retry and health metrics. Reporting must query actual stored time windows.

## V0.5 Intelligence

Versioned analyses, evidence links, clusterable events, failure distinct from neutral, bounded model concurrency and spend.

## V0.6 API/Web

FastAPI search and SSE feed; React timeline, topic views and source-provenance detail pages.

## V1.0 Production gate

Backup/restore, failure-injection, load test, security review, release and rollback procedure.
