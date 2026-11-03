# News24 — 新浪财经 7×24 新闻研究系统

[![CI](https://github.com/1998x-stack/7x24/actions/workflows/ci.yml/badge.svg)](https://github.com/1998x-stack/7x24/actions/workflows/ci.yml)

V0.4 adds **a durable single-runner job engine**, persistent schedules, source contract probes and timezone-correct database-driven reports on top of V0.3 SQLite ingestion. This is an experimental research application, **not a market-data SLA or investment advice system**.

## API verification (2026-11-03)

The Sina 7×24 public page still displays dated live news. The unofficial `https://zhibo.sina.com.cn/api/zhibo/feed` remains referenced in maintained third-party code, but a direct live JSON response could not be independently verified in the current environment. **Do not interpret a successful offline fixture or a live webpage as proof that API pagination works.** The documented Sina iNews `live7x24_list` is a different, authenticated interface and needs authorized `app_key` and signing.

V0.4 exposes `news24 source-probe`, which records whether a direct response has valid expected shape, nonempty items and sufficiently recent timestamps. A probe is one page only, not proof of complete history. `zhibo_id` and `type` are transport adapter configuration, not verified API version numbers.

## Install

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
news24 doctor --json
news24 db migrate --db data/news24.sqlite3
```

Migration upgrades existing V0.3 `user_version=1` databases to `2` without recreating news. Back up your database first, using SQLite backup APIs and not just copying a live WAL file.

## Durable job runtime

```bash
# Configure one source poll every 5 minutes, one probe every 6 hours,
# and an 08:00 Asia/Shanghai report for the previous calendar day
news24 jobs install --collect-every 300 --probe-every 21600 \
  --report-at 08:00 --timezone Asia/Shanghai

# Process a single due task (suitable for test/cron)
news24 jobs run

# Run a persistent foreground worker (Ctrl+C stops it)
news24 jobs run --loop --poll-seconds 5

# See queue, leases, failures, source health and report output
news24 jobs status
news24 jobs list
news24 health
news24 source-probe
news24 report daily --date 2026-11-02
news24 report show --date 2026-11-02
```

Install creates stable schedule IDs and is idempotent: rerunning it does **not** change existing schedule configuration. Missed poll intervals are coalesced (at most one outstanding due job per schedule per tick), not indiscriminately replayed.

Tasks are **at-least-once**; article upserts and report keys must remain idempotent. A crash after a side effect but before completion acknowledgement can produce a retry. Leases, bounded attempts and atomic claims prevent most accidental overlap. Run a single active worker and do not recover unexpired work. No distributed scheduling or external broker is provided.

**An `analyze` job kind is reserved but does not contain an AI executor in V0.4.** Explicit analyze tasks fail rather than being counted as successful. AI model-based analysis belongs in V0.5.

## Reporting and validation

Daily reports query **the complete stored time window**, using a Shanghai-local calendar day and UTC-normalized comparisons; only displayed news samples are capped. Report totals are not calculated from the latest fetch page. Reports have stable keys, revision history and deterministic regeneration.

Every report is explicitly marked **UNVERIFIED** for upstream source coverage. Neither the latest visible news nor a successful ingestion run proves a full-day backfill. A source failure remains visible as a failed job/probe instead of a fabricated neutral summary.

```bash
make lint typecheck test smoke
docker build -t news24:0.4 .
docker run --rm news24:0.4 doctor --json
```

For details see [V0.4 operations](docs/runbooks/v0.4.md), [ADR-0003](docs/adr/0003-durable-jobs.md), and the [roadmap](docs/architecture/roadmap.md). Legacy collector entrypoints are still present for comparison but not covered by V0.4 operational guarantees.
