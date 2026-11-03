# News24 — 7×24 新闻采集、证据及候选事件研究系统

[![CI](https://github.com/1998x-stack/7x24/actions/workflows/ci.yml/badge.svg)](https://github.com/1998x-stack/7x24/actions/workflows/ci.yml)

Version **0.5.0** introduces optional model-based news analysis over the V0.4 durable task runtime. It is an experimental data/research system, **not a verified source of financial market data, trading signals or factual validation**.

## Architecture and scope

- V0.2: packaged CLI + offline source contract fixtures.
- V0.3: SQLite/WAL, versioned raw source snapshots, idempotent ingest and checkpoints.
- V0.4: durable job queue, leases, retries, source probes and database-window reports.
- **V0.5:** explicit model adapter, versioned structured outputs, exact source evidence spans, candidate event grouping and offline golden tests.
- V0.6 future: interactive API and Web UI, human review and independent event verification.

## Install and upgrade

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
news24 doctor --json
news24 db migrate  # upgrades schema v1/v2 to v3; make a consistent backup first
make lint typecheck test smoke
```

V0.5 migration adds analysis/evidence/cluster tables; historical news, source checkpoints, jobs, and reports are retained. Older News24 binaries will intentionally reject the upgraded schema.

## AI analysis is **opt-in**

No model calls happen on ingest, search, report or source probe. The analyzer requires explicit queueing, explicit model configuration and an `OPENAI_API_KEY` for the OpenAI Responses provider. Model availability/price are provider-specific and must be checked in the target account.

```bash
export OPENAI_API_KEY=...
# choose a Responses-compatible model made available to your API account
news24 intelligence enqueue --uid sina_7x24:4700001 --model YOUR_MODEL_ID
news24 jobs run
news24 intelligence history --uid sina_7x24:4700001
news24 intelligence events --day 2026-11-02
```

To inspect individual evidence spans, read an `analysis_key` from `history`:

```bash
news24 intelligence evidence --key YOUR_ANALYSIS_KEY
```

The worker can also read `NEWS24_ANALYSIS_MODEL` for directly enqueued generic analyze jobs. Unlike the legacy analyzer, a missing credential, malformed response or unsupported source quote **does not turn into a false neutral classification**.

Only **verbatim unique substrings** of the stored normalized source text are labeled `TEXT_MATCH_ONLY`, with exact Python character offsets. Absent and ambiguous quotes remain `NOT_FOUND` or `AMBIGUOUS`. A perfect quote match does **not** demonstrate that the claimed interpretation is logically true. Model output and token usage are versioned with provider, model, prompt version/hash, source revision and input hash.

Candidate events are grouped conservatively by *identical sufficiently specific quotations within the same Shanghai-local calendar day*. They are named **CANDIDATE** rather than verified events. They are filtered against the **current** source revision so an old quote does not survive an upstream correction. No fuzzy semantic clustering or cross-source verification is claimed.

## Reliability and tests

```bash
make test
python -m pytest -q tests/contract/test_evidence_gold.py
news24 jobs status
news24 health
```

Offline CI uses fake model providers; it never consumes API tokens or makes a real model call. Check the live provider contract separately in an authorized environment. A source article can contain prompt-injection text: it must be treated only as untrusted input, never instructions.

See [ADR 0004](docs/adr/0004-model-evidence.md), [V0.5 runbook](docs/runbooks/v0.5.md) and [roadmap](docs/architecture/roadmap.md).
