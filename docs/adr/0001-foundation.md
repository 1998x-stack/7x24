# ADR-0001: V0.2 engineering foundation

Status: Accepted for V0.2

## Context

The previous project has two independent Sina readers, an async API that calls blocking requests, JSON append-only storage without deduplication, a Dockerfile pointing to absent files, and tests that do not protect source-response semantics. Old reports make production-readiness claims unsupported by the evidence they include.

## Decision

1. Keep old `src.main` and `sina7x24_playwright.py` intact as legacy comparison sources.
2. Create installable `news24` package with small synchronous one-page fetch: no fake async promises.
3. Define `NewsArticle` with raw payload and separate normalized text; reject naive timestamps. Invalid source publication times remain null, never current time.
4. Fail explicitly on HTTP, schema, and unsupported category errors. Use synthetic contract fixtures.
5. Run non-root, Chromium-free CLI Docker image. No API port or background daemon is promised in V0.2.
6. Scope new lint and typing checks to new code while executing the existing test suite for regressions.
7. Do not treat JSONL snapshot exports as durable data storage.

## Trade-offs and next decisions

V0.2 deliberately limits the live fetch to one page (up to 50 items). It does not yet implement persistent cursors, transactional checkpoints, database upserts, history backfill, or scheduler coordination. All are V0.3/V0.4 responsibilities. The unversioned upstream interface requires externally verified contract tests before production use.

Avoid adding Neo4j, Kafka, Elasticsearch, or a browser runtime to the base service prematurely.
