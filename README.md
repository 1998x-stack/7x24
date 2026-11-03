# News24 — 7×24 新闻采集与证据研究工作台

[![CI](https://github.com/1998x-stack/7x24/actions/workflows/ci.yml/badge.svg)](https://github.com/1998x-stack/7x24/actions/workflows/ci.yml)

**V1.0 consolidated core:** a local research workbench over durable Sina 7×24 news snapshots, model candidates, exact textual provenance and immutable reviewer decisions. It bundles the previously unmerged V0.4 and V0.5 functionality into a single PR to `main`.

This is a **research prototype**, not a production-verified market-data feed, automated fact-checker or trading product.

## What's implemented

| Layer | Capability |
|---|---|
| Data capture (V0.3) | SQLite WAL, raw source page snapshots, article revisions, source checkpoints |
| Jobs (V0.4) | Durable queue, atomic claim, retry, lease recovery, schedules, source probes |
| Intelligence (V0.5) | Opt-in OpenAI Responses adapter, strict analysis models, exact source evidence spans, conservative event candidates |
| Local Workbench (V1.0) | Responsive browser UI, news search, article text with highlighted evidence, analysis history, candidate events, job status and evaluation records |
| Review audit (V1.0) | Token-protected claim/event decisions, immutable append-only reviews, source revision fencing, version-based conflict rejection |
| Quality gate (V1.0) | Source quotation golden corpus evaluation, deterministic metrics, readiness report, HTTP and Chromium E2E tests |

## Local quick start

Requires Python 3.11+ and SQLite FTS5 trigram support.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
news24 doctor --json

# Back up an existing SQLite database safely before migration
news24 db migrate --db data/news24.sqlite3
news24 audit --db data/news24.sqlite3
```

**Start the web interface (loopback ONLY):**

```bash
# read-only interface when NEWS24_REVIEW_TOKEN is not set
news24 web serve --db data/news24.sqlite3 --port 8765
# open http://127.0.0.1:8765/
```

To enable human reviews, set a long, random secret in the **terminal environment**, not in the repository or a public URL. The web interface accepts it only through the password field, keeps it in memory while that tab is open, and does not write it to browser storage:

```bash
export NEWS24_REVIEW_TOKEN='replace-with-a-long-random-operator-secret'
export NEWS24_REVIEWER='local-operator'
news24 web serve --db data/news24.sqlite3 --port 8765
```

The server deliberately **rejects public binds** (e.g. `0.0.0.0`). It does not implement a public auth system or HTTPS. Only use on a trusted workstation; do not expose it through a public reverse proxy.

## News collection, task runtime and AI

```bash
news24 source-probe
news24 ingest --category all --max-pages 50
news24 jobs install --collect-every 300 --probe-every 21600 \
  --report-at 08:00 --timezone Asia/Shanghai
news24 jobs run --loop --poll-seconds 5

# AI is strictly opt-in and requires configured API access and a model ID
news24 intelligence enqueue --uid sina_7x24:4700001 --model YOUR_MODEL_ID
news24 jobs run
news24 intelligence history --uid sina_7x24:4700001
news24 intelligence events
```

V0.5 analysis classifies source wording and extracts **candidate** claims. The exact source quote checker can return TEXT_MATCH_ONLY, NOT_FOUND, or AMBIGUOUS. A quote match proves an occurrence in the stored text, **not** that the interpretation or real-world assertion is true. AI results never overwrite the original news or human reviews.

## Independent local evaluation

```bash
news24 evaluate evidence --dataset tests/fixtures/intelligence/evidence_gold.json
news24 audit
python -m pytest -q tests/unit tests/contract tests/integration tests/test_system.py
```

The quality gate is explicitly limited to **literal quote-match correctness**. A clean result does not establish source completeness, model accuracy, or independent-source corroboration. Runtime probe freshness is only the last known source status.

For a real browser test, install Playwright, install its Chromium browser, then run:

```bash
python -m pip install -e '.[dev,browser]'
python -m playwright install chromium
python -m pytest -q tests/e2e
```

The Chromium test uses an offline local HTTP server and fake model responses, never the live Sina feed or paid AI API.

## Database and backwards compatibility

Schema migrations are additive through `user_version=4`. V1.0 retains the V0.3 article, raw snapshots and checkpoint tables, V0.4 jobs and reports, and V0.5 analysis/event history. It adds immutable human review logs and evaluation records. Older binaries deliberately refuse databases with newer schema. Backup first; rollback means restoring the previous consistent backup, not editing `PRAGMA user_version`.

## Operational boundaries

- Sina's unofficial endpoint is not independently verified for current pagination and access. `source-probe` is a one-page check, **not** proof of 24-hour coverage.
- Model calls, billing and privacy require separate account-specific validation; no production budget enforcement or independent fact verification is claimed.
- The Workbench is local only, without multi-tenant permissions or external accessibility audit.
- Initial long-history backfill remains bounded in memory by page limits. Event clustering uses exact sufficiently long quotes, not independent semantic equivalence.
- No trading signals or investment recommendations.

Documentation: [V1.0 runbook](docs/runbooks/v1.0.md), [API contract](docs/architecture/workbench-api.md), [security/review ADR](docs/adr/0005-local-review-workbench.md), [roadmap](docs/architecture/roadmap.md).
