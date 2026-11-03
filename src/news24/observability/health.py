"""Observable Sina source contract checks; does not imply an official SLA."""

from datetime import UTC, datetime
from typing import Any

from news24.jobs.store import utc_time
from news24.sources.sina.async_client import SinaFeedClient
from news24.storage.database import SQLiteNewsStore


async def probe_sina(
    store: SQLiteNewsStore,
    client: SinaFeedClient,
    *,
    now: datetime | None = None,
    max_age_seconds: int = 14400,
) -> dict[str, Any]:
    """Record source accessibility, schema and freshness, even on probe failure."""
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    current = now or datetime.now(UTC)
    checked_at = utc_time(current)
    status = "ERROR"
    count: int | None = None
    newest: str | None = None
    age: float | None = None
    error: str | None = None
    try:
        page = await client.fetch_page("all", 1, 20)
        count = len(page.articles)
        timestamps = [
            row.published_at.astimezone(UTC)
            for row in page.articles if row.published_at is not None
        ]
        if not page.articles:
            status = "EMPTY"
        elif not timestamps:
            status = "ERROR"
            error = "all returned publication timestamps were invalid or missing"
        else:
            most_recent = max(timestamps)
            newest = utc_time(most_recent)
            age = (current.astimezone(UTC) - most_recent).total_seconds()
            status = "STALE" if age > max_age_seconds or age < -300 else "OK"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"[:1024]
    store.migrate()
    store.conn.execute(
        """INSERT INTO source_probes (
             source, checked_at, status, articles_seen,
             newest_published_at, age_seconds, error_message
           ) VALUES ('sina_7x24', ?, ?, ?, ?, ?, ?)""",
        (checked_at, status, count, newest, age, error),
    )
    return {
        "source": "sina_7x24", "checked_at": checked_at, "status": status,
        "articles_seen": count, "newest_published_at": newest,
        "age_seconds": age, "error": error,
        "note": "one-page direct endpoint probe; not a verified source SLA",
    }


def runtime_health(store: SQLiteNewsStore) -> dict[str, Any]:
    """Read database-backed health; no assumption about active network access."""
    from news24.jobs.store import JobStore

    store.migrate()
    row = store.conn.execute(
        """SELECT checked_at, status, articles_seen, error_message
           FROM source_probes WHERE source='sina_7x24'
           ORDER BY checked_at DESC, probe_id DESC LIMIT 1"""
    ).fetchone()
    last_ingest = store.conn.execute(
        """SELECT status, finished_at FROM ingestion_runs
           ORDER BY started_at DESC, rowid DESC LIMIT 1"""
    ).fetchone()
    return {
        "database": "OK", "schema_version": 3,
        "job_counts": JobStore(store).counts(),
        "last_source_probe": dict(row) if row is not None else None,
        "last_ingestion": dict(last_ingest) if last_ingest is not None else None,
        "warning": "health is only as fresh as the last completed job or probe",
    }
