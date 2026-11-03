"""Durable ingest and backfill tasks: only storage commits advance state."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from news24.sources.sina.async_client import SinaFeedClient
from news24.sources.sina.pagination import fetch_pages
from news24.storage.database import SQLiteNewsStore


async def run_ingestion(
    store: SQLiteNewsStore,
    source: SinaFeedClient,
    *,
    category: str = "all",
    max_pages: int = 10,
    page_size: int = 50,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, Any]:
    store.migrate()
    run_id = uuid4().hex
    before = store.begin_run(run_id, "sina_7x24", category)
    try:
        batch = await fetch_pages(
            source,
            category=category,
            since_id=None if start is not None or end is not None else before,
            max_pages=max_pages,
            page_size=page_size,
            start=start,
            end=end,
        )
        return store.apply_batch(run_id, "sina_7x24", category, batch)
    except Exception as exc:
        store.finish_failed(run_id, exc)
        raise
