"""Stable command line entrypoint: explicit exit codes and machine-readable results."""

import argparse
import asyncio
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from collections import deque
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from news24 import __version__
from news24.core.errors import News24Error
from news24.core.models import NewsArticle
from news24.ingestion.service import run_ingestion
from news24.intelligence.service import analysis_history, evidence_for, event_candidates
from news24.jobs.scheduler import ScheduleStore
from news24.jobs.store import JobStore
from news24.jobs.worker import JobWorker
from news24.observability.health import probe_sina, runtime_health
from news24.reporting.service import generate_daily_report, get_report
from news24.sources.sina.async_client import SinaFeedClient
from news24.sources.sina.client import fetch_latest
from news24.sources.sina.parser import parse_feed, parse_payload
from news24.storage.database import SQLiteNewsStore


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _doctor(args: argparse.Namespace) -> int:
    data_dir = Path(os.getenv("NEWS24_DATA_DIR", "./data")).resolve()
    checks: dict[str, bool] = {}
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=data_dir):
            pass
        checks["data_dir_writable"] = True
    except OSError:
        checks["data_dir_writable"] = False

    try:
        with sqlite3.connect(":memory:") as connection:
            connection.execute("CREATE VIRTUAL TABLE probe USING fts5(body, tokenize='trigram')")
        checks["sqlite_fts5_trigram"] = True
    except sqlite3.Error:
        checks["sqlite_fts5_trigram"] = False
    checks["python_3_11_or_newer"] = sys.version_info >= (3, 11)

    ok = all(checks.values())
    _print({
        "version": __version__,
        "ok": ok,
        "checks": checks,
        "data_dir": str(data_dir),
        "note": "offline environment check; does not verify Sina reachability",
    })
    return 0 if ok else 1


def _atomic_jsonl(path: Path, items: list[NewsArticle], force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite {path}; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
        ) as handle:
            tmp_path = Path(handle.name)
            for item in items:
                handle.write(item.model_dump_json() + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        if not force and path.exists():
            raise FileExistsError(f"refusing to overwrite {path}; pass --force")
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def _collect(args: argparse.Namespace) -> int:
    if args.output and Path(args.output).exists() and not args.force:
        raise FileExistsError("output exists; use --force to replace")
    articles = fetch_latest(args.category, args.limit)
    if args.output:
        _atomic_jsonl(Path(args.output), articles, args.force)
        _print({"ok": True, "count": len(articles), "output": args.output})
    else:
        for article in articles:
            print(article.model_dump_json())
    return 0


def _inspect(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as file:
        rows = deque((line for line in file if line.strip()), maxlen=args.limit)
    articles = [NewsArticle.model_validate_json(row) for row in rows]
    _print({"ok": True, "count": len(articles), "items": [
        {"uid": a.uid, "published_at": a.published_at.isoformat()
         if a.published_at else None, "text": a.content_text[:120]}
        for a in articles
    ]})
    return 0


def _test_fixtures(args: argparse.Namespace) -> int:
    path = Path(args.path)
    articles = parse_feed(
        parse_payload(path.read_text(encoding="utf-8")),
        datetime(2026, 3, 3, tzinfo=UTC),
    )
    if not articles:
        raise ValueError("fixture contains no news; expected a populated golden fixture")
    _print({"ok": True, "count": len(articles), "first_uid": articles[0].uid})
    return 0




def _database(args: argparse.Namespace) -> int:
    with SQLiteNewsStore(args.db) as store:
        version = store.migrate()
        if args.db_action == "migrate":
            _print({"ok": True, "schema_version": version, "db": args.db})
        elif args.db_action == "stats":
            _print({"ok": True, "schema_version": version, **store.statistics()})
        elif args.db_action == "recent":
            _print({"ok": True, "items": [
                a.model_dump(mode="json") for a in store.recent(args.limit)
            ]})
        elif args.db_action == "search":
            _print({"ok": True, "items": [
                a.model_dump(mode="json") for a in store.search(args.query, args.limit)
            ]})
        elif args.db_action == "revisions":
            _print({"ok": True, "items": store.revisions(args.uid)})
        elif args.db_action == "recover":
            _print({"ok": True, "recovered": store.recover_interrupted()})
    return 0


def _date(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("date range must use explicit timezone offset, e.g. +08:00")
    return parsed


async def _async_ingest(args: argparse.Namespace) -> dict[str, object]:
    async with httpx.AsyncClient(
        timeout=15.0,
        follow_redirects=False,
        headers={"Referer": "https://finance.sina.com.cn/7x24/"},
    ) as client:
        source = SinaFeedClient(client, delay=args.delay)
        with SQLiteNewsStore(args.db) as store:
            return await run_ingestion(
                store, source, category=args.category,
                max_pages=args.max_pages, page_size=args.page_size,
                start=_date(getattr(args, "start", None)),
                end=_date(getattr(args, "end", None)),
            )


def _ingest(args: argparse.Namespace) -> int:
    result = asyncio.run(_async_ingest(args))
    _print(result)
    # An incomplete backfill is not a confirmed successful run.
    return 3 if result["status"] == "INCOMPLETE" else 0

def _health(args: argparse.Namespace) -> int:
    with SQLiteNewsStore(args.db) as store:
        _print(runtime_health(store))
    return 0


def _report(args: argparse.Namespace) -> int:
    day = date.fromisoformat(args.date)
    with SQLiteNewsStore(args.db) as store:
        if args.report_action == "daily":
            _print(generate_daily_report(store, day, timezone=args.timezone))
        else:
            markdown = get_report(store, day, timezone=args.timezone)
            if markdown is None:
                raise ValueError("report not found; generate it first")
            print(markdown, end="")
    return 0


async def _probe_once(db_path: str) -> dict[str, object]:
    with SQLiteNewsStore(db_path) as store:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=False,
            headers={"Referer": "https://finance.sina.com.cn/7x24/"},
        ) as client:
            return await probe_sina(store, SinaFeedClient(client))


def _probe(args: argparse.Namespace) -> int:
    result = asyncio.run(_probe_once(args.db))
    _print(result)
    return 0 if result["status"] == "OK" else 3


def _jobs(args: argparse.Namespace) -> int:
    with SQLiteNewsStore(args.db) as store:
        store.migrate()
        jobs = JobStore(store)
        now = datetime.now(UTC)
        if args.jobs_action == "install":
            schedules = ScheduleStore(jobs)
            schedules.install_interval(
                "sina-all", "collect",
                {"category": "all", "max_pages": args.max_pages},
                seconds=args.collect_every, now=now,
            )
            schedules.install_interval(
                "sina-probe", "probe", {"max_age_seconds": 14400},
                seconds=args.probe_every, now=now,
            )
            schedules.install_daily(
                "daily-news", "report", {},
                hhmm=args.report_at, timezone=args.timezone, now=now,
            )
            _print({"ok": True, "installed": [
                "sina-all", "sina-probe", "daily-news",
            ], "note": "install is idempotent; existing schedules are unchanged"})
        elif args.jobs_action == "enqueue":
            payload = json.loads(args.payload)
            if not isinstance(payload, dict):
                raise ValueError("job payload must be a JSON object")
            inserted = jobs.enqueue(
                args.key, args.kind, payload, now=now,
                max_attempts=args.max_attempts,
            )
            _print({"ok": True, "enqueued": inserted, "job_key": args.key})
        elif args.jobs_action == "list":
            _print({"ok": True, "jobs": jobs.latest(args.limit)})
        elif args.jobs_action == "status":
            _print({"ok": True, "counts": jobs.counts()})
        elif args.jobs_action == "recover":
            _print({"ok": True, "recovered": jobs.recover_expired(now=now)})
        elif args.jobs_action == "run":
            worker = JobWorker(store)
            if args.loop:
                count = asyncio.run(
                    worker.serve(poll_seconds=args.poll_seconds, max_jobs=args.max_jobs)
                )
                _print({"ok": True, "processed": count})
            else:
                result = asyncio.run(worker.run_once())
                _print(result)
                if result["state"] == "RETRY_WAIT":
                    return 3
                if result["state"] == "FAILED":
                    return 1
    return 0


def _intelligence(args: argparse.Namespace) -> int:
    with SQLiteNewsStore(args.db) as store:
        store.migrate()
        if args.intelligence_action == "enqueue":
            version = store.conn.execute(
                "SELECT revision_hash FROM news WHERE uid=?", (args.uid,)
            ).fetchone()
            if version is None:
                raise ValueError(f"unknown article: {args.uid}")
            payload = {"uid": args.uid, "provider": "openai", "model": args.model}
            digest = hashlib.sha256(
                (args.uid + "|" + str(version["revision_hash"]) + "|"
                 + args.model).encode("utf-8")
            ).hexdigest()
            key = "analyze:" + digest
            inserted = JobStore(store).enqueue(
                key, "analyze", payload, now=datetime.now(UTC)
            )
            _print({"ok": True, "enqueued": inserted, "job_key": key})
        elif args.intelligence_action == "history":
            _print({"ok": True, "analyses": analysis_history(store, args.uid)})
        elif args.intelligence_action == "evidence":
            _print({"ok": True, "evidence": evidence_for(store, args.key)})
        else:
            _print({
                "ok": True,
                "status": "CANDIDATE_ONLY",
                "events": event_candidates(store, day=args.day, limit=args.limit),
            })
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="news24")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="run local, offline readiness checks")
    doctor.add_argument("--json", action="store_true", help="JSON output (default)")
    doctor.set_defaults(func=_doctor)

    collect = subparsers.add_parser("collect", help="fetch at most one live feed page")
    collect.add_argument("--source", choices=["sina"], default="sina")
    collect.add_argument("--category", default="all")
    collect.add_argument("--limit", type=int, default=20)
    collect.add_argument("--output", help="optional JSONL output path")
    collect.add_argument("--force", action="store_true", help="replace existing output")
    collect.set_defaults(func=_collect)

    inspect = subparsers.add_parser("inspect", help="inspect saved canonical JSONL")
    inspect.add_argument("path")
    inspect.add_argument("--limit", type=int, default=20)
    inspect.set_defaults(func=_inspect)

    fixtures = subparsers.add_parser("test-fixtures", help="validate a Sina response fixture")
    fixtures.add_argument("path")
    fixtures.set_defaults(func=_test_fixtures)

    default_db = str(Path(os.getenv("NEWS24_DATA_DIR", "./data")) / "news24.sqlite3")
    db = subparsers.add_parser("db", help="SQLite schema and inspection")
    actions = db.add_subparsers(dest="db_action", required=True)
    for action in ("migrate", "stats", "recent", "search", "revisions", "recover"):
        command = actions.add_parser(action)
        command.add_argument("--db", default=default_db)
        if action in ("recent", "search"):
            command.add_argument("--limit", type=int, default=20)
        if action == "search":
            command.add_argument("query")
        if action == "revisions":
            command.add_argument("uid")
        command.set_defaults(func=_database)

    for action in ("ingest", "backfill"):
        command = subparsers.add_parser(action)
        command.add_argument("--source", choices=["sina"], default="sina")
        command.add_argument("--category", default="all")
        command.add_argument("--db", default=default_db)
        command.add_argument("--max-pages", type=int, default=10)
        command.add_argument("--page-size", type=int, default=50)
        command.add_argument("--delay", type=float, default=0.5)
        if action == "backfill":
            command.add_argument("--start", required=True)
            command.add_argument("--end")
        command.set_defaults(func=_ingest)

    runtime_db = str(Path(os.getenv("NEWS24_DATA_DIR", "./data")) / "news24.sqlite3")
    report = subparsers.add_parser("report", help="reproducible stored-news reports")
    report_sub = report.add_subparsers(dest="report_action", required=True)
    for action in ("daily", "show"):
        command = report_sub.add_parser(action)
        command.add_argument("--date", required=True)
        command.add_argument("--timezone", default="Asia/Shanghai")
        command.add_argument("--db", default=runtime_db)
        command.set_defaults(func=_report)

    health = subparsers.add_parser("health", help="database-backed runtime status")
    health.add_argument("--db", default=runtime_db)
    health.set_defaults(func=_health)

    probe = subparsers.add_parser("source-probe", help="one live source contract check")
    probe.add_argument("--db", default=runtime_db)
    probe.set_defaults(func=_probe)

    jobs = subparsers.add_parser("jobs", help="durable queue and schedules")
    job_sub = jobs.add_subparsers(dest="jobs_action", required=True)
    for action in ("install", "enqueue", "run", "list", "status", "recover"):
        command = job_sub.add_parser(action)
        command.add_argument("--db", default=runtime_db)
        if action == "install":
            command.add_argument("--collect-every", type=int, default=300)
            command.add_argument("--probe-every", type=int, default=21600)
            command.add_argument("--report-at", default="08:00")
            command.add_argument("--timezone", default="Asia/Shanghai")
            command.add_argument("--max-pages", type=int, default=10)
        if action == "enqueue":
            command.add_argument("--key", required=True)
            command.add_argument(
                "--kind", choices=["collect", "report", "probe", "analyze"], required=True
            )
            command.add_argument("--payload", default="{}")
            command.add_argument("--max-attempts", type=int, default=3)
        if action == "run":
            command.add_argument("--loop", action="store_true")
            command.add_argument("--poll-seconds", type=float, default=5.0)
            command.add_argument("--max-jobs", type=int)
        if action == "list":
            command.add_argument("--limit", type=int, default=20)
        command.set_defaults(func=_jobs)
    intelligence = subparsers.add_parser(
        "intelligence", help="versioned model results and grounded evidence"
    )
    intelligence_sub = intelligence.add_subparsers(
        dest="intelligence_action", required=True
    )
    for action in ("enqueue", "history", "evidence", "events"):
        command = intelligence_sub.add_parser(action)
        command.add_argument("--db", default=runtime_db)
        if action in ("enqueue", "history"):
            command.add_argument("--uid", required=True)
        if action == "enqueue":
            command.add_argument("--model", required=True)
        if action == "evidence":
            command.add_argument("--key", required=True)
        if action == "events":
            command.add_argument("--day")
            command.add_argument("--limit", type=int, default=50)
        command.set_defaults(func=_intelligence)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "limit", 1) < 1:
        parser.error("--limit must be positive")
    try:
        return int(args.func(args))
    except (OSError, ValueError, RuntimeError, sqlite3.Error, News24Error) as exc:
        print(f"news24: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
