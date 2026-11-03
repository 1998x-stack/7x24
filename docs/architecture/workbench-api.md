# Workbench V1 API contract (local-only)

All GET responses are JSON (`application/json`) except `/`, `/app.css` and `/app.js`. API routes do not support CORS and are bound to 127.0.0.1. All dynamic paths use query parameters; paths are not interpreted as filesystem paths.

## Read endpoints

| Route | Parameters | Result |
|---|---|---|
| GET /api/health | — | DB/schema, queue counts and last source probe/ingestion |
| GET /api/news | q, limit=30 (1..100), offset=0 | article previews and independent total count |
| GET /api/article | uid | raw canonical stored article and current revision hash |
| GET /api/analyses | uid | model/provider and source-version analysis history |
| GET /api/evidence | key=analysis_key | source quotes, exact spans and latest human review per claim |
| GET /api/events | day?, limit=50 (1..200) | conservative candidate events, **not** verified event catalog |
| GET /api/event | key=event_key | current source-revision members and review history |
| GET /api/jobs | limit=30 (1..100) | bounded queue metadata; raw job payloads intentionally hidden |
| GET /api/evaluations | — | latest offline lexical-golden evaluation summaries |

Missing results return 404, malformed parameters 422. API errors never echo database internals. Content is always rendered via safe DOM `textContent`; source HTML is never interpreted as active markup.

## Write endpoints (optional operator mode)

Both endpoints require `Origin: http://127.0.0.1:<port>` matching `Host`, `Authorization: Bearer <NEWS24_REVIEW_TOKEN>`, JSON content type, and body not exceeding 16KiB. The token is configured in the server environment, compared with `hmac.compare_digest` and never persisted in browser storage.

- POST `/api/reviews/claim`: `analysis_key`, `claim_index`, `expected_version`, `expected_source_revision`, `decision`, `reason`. Decisions: `SUPPORTED_BY_TEXT`, `NOT_SUPPORTED_BY_TEXT`, `NEEDS_INVESTIGATION`.
- POST `/api/reviews/event`: `event_key`, `expected_version`, `decision`, `reason`. Decisions: `RELATED`, `NOT_RELATED`, `NEEDS_INVESTIGATION`.

Success: 201 with new monotonically increasing review version. Unauthorized: 401; disabled/wrong origin/host: 403; conflict/stale revision: 409; malformed request: 422. Claims cannot be approved if the source quote lacks a unique text match. Every review creates a new immutable audit record; no DELETE/PUT endpoints.

No server-side model creation endpoint is exposed: model calls must be explicitly queued through the CLI.
