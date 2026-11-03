# ADR-0002: Transactional SQLite ingest and fail-closed watermarks

Status: proposed for V0.3. Replaces JSON append-only for the NEW ingestion path; the historical CLI remains available.

## Decision

- SQLite/WAL, one local writer; FTS5 trigram; SQL migration version 1 bundled with the package.
- Article identity is `(source, source_id)`; the canonical record retains both raw payload and normalized article JSON.
- A semantic content update or delete flag creates an immutable revision. Repeated polling is idempotent (retrieval timestamp excluded from revision hash).
- One transaction saves complete page JSON snapshots, news upserts, revisions, category relations, run accounting and checkpoint advancement.
- The watermark may advance **only** if the pager sees an old checkpoint, an empty page, the known last page, or a validated backfill date boundary.
- Page-number/ID ordering violations and network failures stop processing without moving the watermark.
- On hitting max_pages without coverage evidence, new articles persist but the run remains INCOMPLETE, return code 3.
- Backfill date ranges never advance the real-time high-water ID.
- Failures and cancelled processes leave visible job/run history; admin-only `db recover` marks abandoned attempts failed.

## Known limitations

An upstream page may mutate between requests, which no simple pagination scheme can fully correct without stable server-side cursors. Corrections older than the observed overlap need a deeper replay. Initial historical bootstrapping may need many pages and therefore large memory; V0.4 should stream immutable page batches to durable staging and improve source verification. Multi-node concurrency is unsupported. Raw news should not be rendered as trusted HTML.
