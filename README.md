# News24 · Evidence-first news research workbench

[![CI](https://github.com/1998x-stack/7x24/actions/workflows/ci.yml/badge.svg)](https://github.com/1998x-stack/7x24/actions/workflows/ci.yml)

A local, provenance-first 7×24 news collection and research system. The supported runtime is a **Python 3.11+ modular monolith**: typed news contracts, durable SQLite/WAL ingestion, explicit AI analysis, evidence/audit review, job scheduling and a localhost workbench. The unofficial source API and real model quality are **not production-verified**.

> **V1.1 structure refactor:** This release reorganizes implementation code into four boundaries, isolates experimental legacy code, keeps the `news24` CLI and compatibility imports working, and adds dependency-boundary and wheel-content tests. It is a structural refactor, not a new data provider or AI capability claim.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
news24 doctor --json
news24 db migrate
news24 web serve --port 8765
```

Open `http://127.0.0.1:8765/` on the same machine. This is **read-only by default**. Operator review requires a separately configured `NEWS24_REVIEW_TOKEN`; the server refuses non-loopback binds and is not multi-user auth.

To enable model analysis, install `python -m pip install -e '.[llm]'`, configure an API key in the runtime environment (never commit secrets), and explicitly enqueue an item using `news24 intelligence enqueue --uid ... --model ...`. Ingestion, search and reporting do **not** automatically call paid models.

## Repository layout

```text
7x24/
├── .github/
│   ├── workflows/                   CI, browser E2E, wheel checks
│   ├── ISSUE_TEMPLATE/             Maintainer issue intake
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── dependabot.yml
├── docs/
│   ├── architecture/               Architecture and API contracts
│   ├── adr/                        Decision records
│   ├── runbooks/                   Operations / migrations
│   ├── development/                Local workflow and testing
│   └── archive/                    Historical reports
├── examples/sina/                  Historical data examples, not API fixtures
├── legacy/                         Frozen pre-V0.2 scripts / implementation
├── scripts/                        Maintainer quality tools
├── src/news24/                     Only shipped production package
│   ├── domain/                     News, ingestion and analysis contracts
│   ├── application/                Collection, jobs, evidence, reports, review
│   ├── infrastructure/             SQLite, Sina transport, LLM adapters
│   ├── interfaces/                 CLI and packaged localhost Web
│   ├── core/, ingestion/, ...      Compatibility imports for existing callers
│   └── __main__.py
├── tests/
│   ├── unit/, contract/, integration/
│   ├── architecture/               Dependency and package-data safeguards
│   ├── e2e/                        Real local Chromium interaction
│   ├── legacy/                     Historical pipeline regression tests
│   └── fixtures/
├── pyproject.toml
├── Dockerfile
├── compose.yaml
└── Makefile
```

See [architecture overview](docs/architecture/overview.md) for dependencies, design decisions, compatibility policy and source ownership. New code must use the canonical `news24.domain`, `news24.application`, `news24.infrastructure` or `news24.interfaces` paths. Old `news24.core` and other former module paths remain forwarders for existing imports; **do not add new imports through them**.

## Common commands

```bash
news24 db migrate
news24 ingest --category all --max-pages 50
news24 source-probe
news24 jobs install --collect-every 300 --probe-every 21600 --report-at 08:00
news24 jobs run --loop --poll-seconds 5
news24 report daily --date 2026-11-02
news24 intelligence events
news24 audit
```

Daily reports reflect the locally stored calendar-day window, not guaranteed complete upstream news. The evidence checker verifies exact text occurrence, not independent factual entailment. Events are candidates only; no investment signals are implied.

## Development & quality

```bash
python -m pip install -e '.[dev]'
make lint typecheck test smoke
# Optional Chromium UI checks
python -m pip install -e '.[dev,browser]'
python -m playwright install chromium
make browser
# Wheel package/resource check
make build
python scripts/verify_wheel.py dist
```

CI checks Python 3.11/3.12, architecture contracts, historical regression compatibility, browser E2E, Docker and distributable wheel contents. The core installation uses `httpx` and `pydantic`; the OpenAI SDK and historical pipeline dependencies are optional extras. Historical scripts live under [legacy/](legacy/README.md) and are excluded from the wheel.

See [CONTRIBUTING.md](CONTRIBUTING.md) for coding workflow, [SECURITY.md](SECURITY.md) for reporting security issues, [CHANGELOG.md](CHANGELOG.md) for migration notes, and [V1.0 runbook](docs/runbooks/v1.0.md) for the current local operational guarantees.

## Limitations

The Sina endpoint has no verified SLA/complete-history guarantee in this environment. Live model availability, cost, privacy, semantic factual accuracy and public identity/security are separate gates. Never expose the local workbench or review token via an external reverse proxy without an independently reviewed authentication and TLS layer.
