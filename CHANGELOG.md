# Changelog

Project history is preserved in GitHub pull requests and historical ADRs. This file summarizes the supported runtime transitions.

## Unreleased — V1.1 repository and architecture refactor

- Canonical package boundaries: domain, application, infrastructure and interfaces.
- Backwards-compatible `news24.*` import facades and unchanged CLI command syntax.
- Legacy pre-V0.2 pipeline quarantined under `legacy/`, historical regression moved to `tests/legacy`.
- Historical sample files and old status reports moved from root to examples/archive.
- Single canonical location for versioned SQL migrations and shipped Web assets.
- Minimal default install with optional `llm` and `legacy` extras; architecture and wheel-content CI gates.
- GitHub templates, contributor instructions and security disclosure policy.

## V1.0 consolidated core

- SQLite-backed durable ingestion, jobs, reports, evidence intelligence, candidate events and immutable operator reviews.
- Local provenance Workbench with browser end-to-end checks and honest offline readiness diagnostics.

## V0.2–V0.5

See `docs/adr/`, `docs/runbooks/` and merged GitHub PRs for incremental migration details.

### Compatibility

Python entrypoint `news24` is stable; old `news24.core`, `news24.ingestion`, `news24.storage` and similar import paths forward to canonical implementations. Historical import paths `src.*` are not shipped in the wheel; run those only from the checked-out `legacy/` tree. An older News24 executable refuses databases with a newer schema version by design.
