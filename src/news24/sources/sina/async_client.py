"""Reusable async HTTP transport for Sina feed pages; mockable in offline CI."""

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx

from news24.core.errors import SourceSchemaError, SourceUnavailable
from news24.ingestion.models import FeedPage
from news24.sources.sina.categories import category_id
from news24.sources.sina.client import FEED_URL
from news24.sources.sina.parser import parse_feed, parse_payload


class SinaFeedClient:
    """One async HTTPX client; caller owns connection pool and lifetime."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        url: str = FEED_URL,
        delay: float = 0.5,
        retries: int = 2,
    ) -> None:
        if delay < 0 or retries < 0 or retries > 5:
            raise ValueError("delay must be nonnegative, retries must be 0..5")
        self.client = client
        self.url = url
        self.delay = delay
        self.retries = retries

    async def fetch_page(
        self, category: str, page: int, page_size: int = 50
    ) -> FeedPage:
        if page < 1 or not 1 <= page_size <= 50:
            raise ValueError("page must be >=1, page_size must be 1..50")
        params: dict[str, str | int] = {
            "zhibo_id": 152, "tag_id": category_id(category),
            "page": page, "page_size": page_size, "pagesize": page_size,
            "dire": "f", "dpc": 1, "type": 0,
        }
        payload: dict[str, Any] | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await self.client.get(self.url, params=params, timeout=15.0)
                response.raise_for_status()
                payload = parse_payload(response.text)
                break
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                if (code == 429 or 500 <= code < 600) and attempt < self.retries:
                    await asyncio.sleep(min(0.2 * (2 ** attempt), 2))
                    continue
                raise SourceUnavailable(f"Sina HTTP status {code}") from exc
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt < self.retries:
                    await asyncio.sleep(min(0.2 * (2 ** attempt), 2))
                    continue
                raise SourceUnavailable("Sina transport unavailable") from exc
            except httpx.RequestError as exc:
                raise SourceUnavailable("Sina request error") from exc

        if payload is None:
            raise SourceUnavailable("Sina did not provide a response")
        fetched_at = datetime.now(UTC)
        articles = parse_feed(payload, fetched_at)
        try:
            info = payload["result"]["data"]["feed"].get("page_info", {})
            pages = info.get("totalPage")
            actual_page = info.get("page")
        except (KeyError, AttributeError, TypeError) as exc:
            raise SourceSchemaError("invalid pagination metadata") from exc
        if pages is not None and (not isinstance(pages, int) or pages < 0):
            raise SourceSchemaError("invalid totalPage")
        if actual_page is not None and int(actual_page) != page:
            raise SourceSchemaError("source returned an unexpected page number")
        if self.delay:
            await asyncio.sleep(self.delay)
        return FeedPage(
            number=page, fetched_at=fetched_at,
            articles=articles, raw=payload, total_pages=pages,
        )
