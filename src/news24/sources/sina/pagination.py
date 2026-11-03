"""Fail-closed page walk: only proven coverage may advance a watermark."""

from datetime import datetime

from news24.core.errors import SourceSchemaError
from news24.ingestion.models import FetchBatch
from news24.sources.sina.async_client import SinaFeedClient


async def fetch_pages(
    source: SinaFeedClient,
    *,
    category: str,
    since_id: int | None,
    max_pages: int = 10,
    page_size: int = 50,
    start: datetime | None = None,
    end: datetime | None = None,
) -> FetchBatch:
    """Collect descending-ID pages, without advancing on unverified page limits."""
    if max_pages < 1 or not 1 <= page_size <= 50:
        raise ValueError("max_pages must be positive, page_size must be 1..50")
    if start is not None and start.utcoffset() is None:
        raise ValueError("start must be timezone-aware")
    if end is not None and end.utcoffset() is None:
        raise ValueError("end must be timezone-aware")
    if start and end and start >= end:
        raise ValueError("start must precede end")

    backfill = start is not None or end is not None
    batch = FetchBatch(checkpoint_before=since_id, checkpoint_after=None)
    max_seen: int | None = None
    last_id: int | None = None
    seen_ids: set[int] = set()

    for page_number in range(1, max_pages + 1):
        page = await source.fetch_page(category, page_number, page_size)
        batch.pages.append(page)
        ids: list[int] = []
        for article in page.articles:
            try:
                item_id = int(article.source_id)
            except (ValueError, TypeError) as exc:
                raise SourceSchemaError("non-numeric Sina news id") from exc
            ids.append(item_id)
        if len(set(ids)) != len(ids):
            raise SourceSchemaError("duplicate ids within a single feed page")
        if any(a <= b for a, b in zip(ids, ids[1:])):
            raise SourceSchemaError("Sina page is not strictly descending by id")
        if ids and last_id is not None and ids[0] >= last_id:
            raise SourceSchemaError("overlapping/out-of-order pages; checkpoint unsafe")
        if ids:
            last_id = ids[-1]
            max_seen = max(ids[0], max_seen or 0)

        for article, item_id in zip(page.articles, ids):
            if item_id in seen_ids:
                raise SourceSchemaError("repeated id across pages; checkpoint unsafe")
            seen_ids.add(item_id)
            if backfill:
                if article.published_at is not None:
                    if start and article.published_at < start:
                        continue
                    if end and article.published_at >= end:
                        continue
            # Include the overlap page too: revised/deleted old IDs must be replayed.
            batch.articles.append(article)

        if not backfill:
            batch.checkpoint_after = max_seen

        if since_id is not None and not backfill and ids and ids[-1] <= since_id:
            batch.complete = True
            batch.reason = "checkpoint_overlap"
            break

        if backfill and start is not None and page.articles:
            known = [a.published_at for a in page.articles]
            if all(t is not None for t in known):
                times = [t for t in known if t is not None]
                if times == sorted(times, reverse=True) and times[-1] < start:
                    batch.complete = True
                    batch.reason = "date_boundary"
                    break

        if not page.articles:
            batch.complete = True
            batch.reason = "empty_page"
            break

        if page.total_pages is not None and page_number >= page.total_pages:
            batch.complete = True
            batch.reason = "last_page"
            break

    if backfill:
        batch.checkpoint_after = None
    return batch
