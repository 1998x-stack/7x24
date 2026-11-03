# News24 engineering roadmap

## Delivered components

- **V0.2** Packaged Python foundation, typed models, offline contract and CI
- **V0.3** Transactional source ingestion, raw snapshots, article revisions, SQLite FTS5
- **V0.4** Durable job runtime, schedules, retry/lease recovery, live source probe
- **V0.5** Opt-in AI analysis with explicit model, versioned outputs, verbatim evidence spans and candidate events
- **V1.0 core** Local provenance-first browser, token-protected append-only human review, optimistic revision fencing, job and source dashboard, independent lexical baseline, API/browser tests

## Still mandatory before production

1. Independently verify live Sina feed fields, pagination, historical completeness and source rights. Obtain golden authorized real responses and run periodic contract checks.
2. Independently evaluate deployed model availability, privacy, latency, output accuracy and token-cost bounds using a controlled budget. A text quote match is not semantic entailment.
3. Replace local operator token with authenticated per-user identity, audit and TLS when enabling remote access.
4. Long-history streaming/backfill and stable source cursors; event identity independent review and merge/split audit.
5. Real browser cross-platform testing, manual assistive-technology review and operational alerting.

The codebase must never claim production readiness on the basis of offline CI alone.
