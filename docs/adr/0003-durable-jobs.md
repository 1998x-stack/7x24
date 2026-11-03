# ADR-0003: single-runner durable queue and evidence-aware reports

Status: proposed — V0.4

## Decision

- Extend SQLite schema version from 1 to 2 with a backward-compatible migration. Keep the V0.3 news tables intact.
- Persist queued jobs, dedupe keys, attempt history, run leases, interval/daily schedules, generated report revisions, and one-page source contract checks.
- Queue semantics are at-least-once. Claim uses `BEGIN IMMEDIATE` and owner/attempt fencing on completion.
- A timed-out task is retryable with bounded exponential delay; after the configured retry budget, it becomes FAILED.
- Only expired job leases may be recovered automatically. A single active worker remains the supported deployment mode.
- Fixed interval: skip missed intervals after restart, enqueue one current due task, then resume cadence. Daily report: schedule a previous-local-day report at 08:00 Asia/Shanghai.
- No AI-based analysis in V0.4; the analyze task type has no default executor and fails explicitly.
- All daily numbers are generated from SQLite by a timezone-correct [start,end) range. Each report has a stable key and immutable revision records.
- Report `completeness=UNVERIFIED` until independent source coverage evidence exists; no false 24-hour coverage guarantee.
- A source probe distinguishes valid response, empty list, stale content, and source/schema error; direct API availability has not been independently proven.

## Failure semantics

Database transaction failure before news commit leaves source watermark unchanged. A job crash leaves RUNNING until lease expiry; retry can re-execute the underlying idempotent operation. A job that returns INCOMPLETE is retried, not marked successful. The worker times out job handlers before lease expiry.

## Limits

No multi-host leader election, heartbeat renewal, strict exactly-once external side effects, source API SLA, or model analyzer. Live Sina page-number pagination still requires real-world contract verification; mutations between pages are not solved by this version.
