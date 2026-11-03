# ADR 0005 — localhost provenance workbench and immutable human review

Status: proposed for V1.0 integration

## Context

V0.3 news data and revisions, V0.4 job runtime and V0.5 model evidence were only exposed through CLI/SQLite inspection. A browser interface is useful, but any arbitrary visitor must not be allowed to change model review outcomes.

## Decision

Use the standard-library ThreadingHTTPServer as a loopback-only API+static UI for single-workstation operation. No new production web framework, message broker or cloud auth service. Every request opens its own SQLite connection (WAL) and write operations use BEGIN IMMEDIATE to avoid overwriting concurrent decisions.

Static assets are bundled as package data. Content Security Policy disallows inline JS, external assets and active HTML. The frontend renders all upstream/model strings using `textContent` rather than `innerHTML`. Responses include nosniff, referrer and frame protections; no CORS allowed. Host is restricted to localhost/127.0.0.1 and listener only binds 127.0.0.1.

A long configured operator token and matching HTTP Origin are required for claim/event review writes. Browser token remains in a password input and is never saved. There are no public writes, no remote bind, no page-open induced paid model tasks.

Human review is scoped to exact stored source revision, evidence span and integer review version. Logs are append-only, with reviewer operator label from server environment, never client-provided identity. Stale sources and concurrent review conflicts fail rather than overwriting or silently reusing a verdict.

A lexical golden dataset is the baseline quality gate and must never be advertised as semantic fact verification. CLI and UI have a readiness marker `NOT_PRODUCTION_VERIFIED` until authorized external verification.

## Tradeoffs

Single-operator local token is not multi-user authentication or secure remote deployment. Browser/HTTP E2E tests are synthetic. Future production evolution must introduce audited identity, TLS, per-user permissions, rate limiting and independent semantic correctness checks before expanding beyond loopback.
