"""V0.4 integration tests: durable jobs, scheduling, reporting and source probes."""

import hashlib
import sqlite3
from datetime import UTC, date, datetime, timedelta
from importlib import resources
from pathlib import Path

import pytest

from news24.cli import main
from news24.core.models import NewsArticle
from news24.ingestion.models import FeedPage, FetchBatch
from news24.jobs.scheduler import ScheduleStore
from news24.jobs.store import JobStore
from news24.jobs.worker import JobWorker
from news24.observability.health import probe_sina, runtime_health
from news24.reporting.service import generate_daily_report, get_report, report_window
from news24.storage.database import SQLiteNewsStore

NOW = datetime(2026, 11, 3, 0, 0, tzinfo=UTC)


def article(key: int, when: datetime, *, text: str = "宏观经济增长") -> NewsArticle:
    return NewsArticle(
        uid=f"sina_7x24:{key}",
        source="sina_7x24",
        source_id=str(key),
        title=f"新闻{key}",
        content_raw=text,
        content_text=text,
        published_at=when,
        fetched_at=NOW,
        tags=["宏观"],
        categories=["宏观"],
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
        raw={"id": key},
    )


def seed(store: SQLiteNewsStore, records: list[NewsArticle], key: str = "seed") -> None:
    store.migrate()
    store.begin_run(key, "sina_7x24", "all")
    store.apply_batch(key, "sina_7x24", "all", FetchBatch(
        articles=records, complete=True, reason="test", checkpoint_after=None,
    ))


def test_upgrade_v1_to_v3_without_data_loss(tmp_path: Path) -> None:
    path = tmp_path / "old.sqlite3"
    schema = (
        resources.files("news24.storage.migrations")
        .joinpath("0001_initial.sql")
        .read_text(encoding="utf-8")
    )
    with sqlite3.connect(path) as conn:
        conn.executescript(schema + "\nPRAGMA user_version=1;")
    with SQLiteNewsStore(path) as store:
        assert store.migrate() == 4
        assert store.migrate() == 4
        assert store.statistics()["news"] == 0
        assert store.conn.execute(
            "SELECT name FROM sqlite_master WHERE name='job_queue'"
        ).fetchone() is not None
        assert store.conn.execute(
            "SELECT name FROM sqlite_master WHERE name='report_revisions'"
        ).fetchone() is not None


def test_queue_claim_retry_dedupe_and_completion(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "db.sqlite3") as store:
        store.migrate()
        jobs = JobStore(store)
        assert jobs.enqueue("k1", "collect", {"category": "all"}, now=NOW)
        assert not jobs.enqueue("k1", "collect", {"category": "other"}, now=NOW)
        j = jobs.claim("runner-1", now=NOW, lease_seconds=30)
        assert j is not None and j["attempt"] == 1
        assert j["payload"]["category"] == "all"
        assert jobs.claim("runner-2", now=NOW) is None
        assert jobs.fail(j, RuntimeError("network failure"), now=NOW) == "RETRY_WAIT"
        assert jobs.claim("runner-1", now=NOW + timedelta(seconds=4)) is None
        retry = jobs.claim("runner-2", now=NOW + timedelta(seconds=5))
        assert retry is not None and retry["attempt"] == 2
        assert jobs.succeed(retry, {"ok": True}, now=NOW + timedelta(seconds=6)) == "SUCCEEDED"
        assert jobs.get("k1")["state"] == "SUCCEEDED"
        assert jobs.conn.execute("SELECT COUNT(*) FROM job_attempts").fetchone()[0] == 2


def test_stale_lease_recovered_only_after_expiration(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "db.sqlite3") as store:
        store.migrate()
        jobs = JobStore(store)
        jobs.enqueue("recover", "report", {"report_date": "2026-11-02"}, now=NOW)
        claim = jobs.claim("owner", now=NOW, lease_seconds=10)
        assert claim is not None
        assert jobs.recover_expired(now=NOW + timedelta(seconds=9)) == 0
        assert jobs.get("recover")["state"] == "RUNNING"
        assert jobs.recover_expired(now=NOW + timedelta(seconds=10)) == 1
        assert jobs.get("recover")["state"] == "RETRY_WAIT"
        assert jobs.recover_expired(now=NOW + timedelta(seconds=20)) == 0
        with pytest.raises(ValueError, match="stale job completion"):
            jobs.succeed(claim, {"ok": True}, now=NOW + timedelta(seconds=20))


def test_retry_budget_is_bounded(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "db.sqlite3") as store:
        store.migrate()
        jobs = JobStore(store)
        jobs.enqueue("bounded", "probe", {}, now=NOW, max_attempts=2)
        a = jobs.claim("one", now=NOW)
        assert a is not None
        jobs.fail(a, RuntimeError("bad"), now=NOW)
        b = jobs.claim("two", now=NOW + timedelta(seconds=5))
        assert b is not None
        assert jobs.fail(b, RuntimeError("bad"), now=NOW + timedelta(seconds=6)) == "FAILED"
        assert jobs.claim("three", now=NOW + timedelta(hours=1)) is None


def test_scheduler_skips_missed_intervals_and_dedupes(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "db.sqlite3") as store:
        store.migrate()
        jobs = JobStore(store)
        schedules = ScheduleStore(jobs)
        schedules.install_interval("news", "collect", {"category": "all"},
                                   seconds=60, now=NOW)
        later = NOW + timedelta(hours=1)
        assert schedules.tick(now=later) == 1
        assert schedules.tick(now=later) == 0
        assert len(jobs.latest()) == 1
        assert jobs.latest()[0]["kind"] == "collect"
        assert schedules.tick(now=later + timedelta(seconds=60)) == 1


def test_daily_schedule_previous_day_asia_shanghai(tmp_path: Path) -> None:
    prior = NOW - timedelta(hours=1)  # 07:00 in Shanghai
    with SQLiteNewsStore(tmp_path / "db.sqlite3") as store:
        store.migrate()
        jobs = JobStore(store)
        schedules = ScheduleStore(jobs)
        schedules.install_daily("daily", "report", {}, hhmm="08:00",
                                timezone="Asia/Shanghai", now=prior)
        assert schedules.tick(now=prior) == 0
        assert schedules.tick(now=NOW) == 1
        pending = jobs.claim("worker", now=NOW)
        assert pending is not None
        assert pending["payload"]["report_date"] == "2026-11-02"
        assert pending["payload"]["timezone"] == "Asia/Shanghai"


def test_report_calendar_boundaries_idempotency_and_versions(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "db.sqlite3") as store:
        entries = [
            article(1, datetime.fromisoformat("2026-11-01T16:00:00+00:00")),
            article(2, datetime.fromisoformat("2026-11-02T23:59:59+08:00")),
            article(3, datetime.fromisoformat("2026-11-03T00:00:00+08:00")),
            article(4, datetime.fromisoformat("2026-11-01T23:59:59+08:00")),
        ]
        seed(store, entries)
        date_key = date(2026, 11, 2)
        start, end = report_window(date_key, "Asia/Shanghai")
        assert start == datetime.fromisoformat("2026-11-01T16:00:00+00:00")
        assert end == datetime.fromisoformat("2026-11-02T16:00:00+00:00")
        first = generate_daily_report(store, date_key, now=NOW)
        assert first["state"] == "SUCCEEDED" and first["news_count"] == 2
        second = generate_daily_report(store, date_key, now=NOW)
        assert second["state"] == "NO_CHANGES" and second["revision"] == 1
        markdown = get_report(store, date_key)
        assert markdown is not None and "来源覆盖完整性：未验证" in markdown
        assert "新闻1" in markdown and "新闻2" in markdown
        assert "新闻3" not in markdown
        seed(store, [article(5, datetime.fromisoformat("2026-11-02T12:00:00+08:00"))],
             key="seed-more")
        third = generate_daily_report(store, date_key, now=NOW)
        assert third["state"] == "SUCCEEDED" and third["revision"] == 2
        assert third["news_count"] == 3
        assert store.conn.execute(
            "SELECT COUNT(*) FROM report_revisions"
        ).fetchone()[0] == 2


@pytest.mark.asyncio
async def test_worker_executes_report_without_network(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "db.sqlite3") as store:
        seed(store, [article(1, datetime.fromisoformat("2026-11-02T12:00:00+08:00"))])
        jobs = JobStore(store)
        jobs.enqueue("report-1", "report", {
            "report_date": "2026-11-02", "timezone": "Asia/Shanghai",
        }, now=NOW)
        worker = JobWorker(store, clock=lambda: NOW)
        out = await worker.run_once()
        assert out["state"] == "SUCCEEDED"
        assert out["result"]["news_count"] == 1
        assert jobs.get("report-1")["state"] == "SUCCEEDED"
        assert await worker.run_once() == {"state": "IDLE", "owner": worker.owner}


@pytest.mark.asyncio
async def test_worker_incomplete_task_is_retried(tmp_path: Path) -> None:
    async def incomplete(payload: dict) -> dict:
        return {"status": "INCOMPLETE", "reason": "page_limit"}

    with SQLiteNewsStore(tmp_path / "db.sqlite3") as store:
        store.migrate()
        jobs = JobStore(store)
        jobs.enqueue("collect-1", "collect", {}, now=NOW)
        worker = JobWorker(store, handlers={"collect": incomplete}, clock=lambda: NOW)
        output = await worker.run_once()
        assert output["state"] == "RETRY_WAIT"
        assert jobs.get("collect-1")["attempts"] == 1


@pytest.mark.asyncio
async def test_probe_records_ok_stale_and_error(tmp_path: Path) -> None:
    class FakeFeed:
        def __init__(self, *, error: bool = False, old: bool = False) -> None:
            self.error = error
            self.old = old

        async def fetch_page(self, category: str, page: int, size: int) -> FeedPage:
            if self.error:
                raise RuntimeError("source down")
            when = NOW - timedelta(days=1) if self.old else NOW - timedelta(minutes=1)
            return FeedPage(1, NOW, [article(1, when)], {}, 1)

    with SQLiteNewsStore(tmp_path / "db.sqlite3") as store:
        good = await probe_sina(store, FakeFeed(), now=NOW)
        stale = await probe_sina(store, FakeFeed(old=True), now=NOW)
        bad = await probe_sina(store, FakeFeed(error=True), now=NOW)
        assert [good["status"], stale["status"], bad["status"]] == [
            "OK", "STALE", "ERROR",
        ]
        assert store.conn.execute("SELECT COUNT(*) FROM source_probes").fetchone()[0] == 3
        health = runtime_health(store)
        assert health["last_source_probe"]["status"] == "ERROR"


def test_v04_cli_offline_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = str(tmp_path / "db.sqlite3")
    assert main(["db", "migrate", "--db", db]) == 0
    assert main(["jobs", "status", "--db", db]) == 0
    assert main(["jobs", "install", "--db", db]) == 0
    assert main(["health", "--db", db]) == 0
    assert main(["report", "daily", "--date", "2026-11-02", "--db", db]) == 0
    assert main(["report", "show", "--date", "2026-11-02", "--db", db]) == 0
    assert "未验证" in capsys.readouterr().out
