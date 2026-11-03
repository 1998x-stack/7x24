"""Small synchronous CLI HTTP adapter; async pagination is scheduled for V0.3."""

from datetime import UTC, datetime

import httpx

from news24.core.errors import SourceUnavailable
from news24.core.models import NewsArticle
from news24.sources.sina.categories import category_id
from news24.sources.sina.parser import parse_feed, parse_payload

FEED_URL = "https://zhibo.sina.com.cn/api/zhibo/feed"


def fetch_latest(
    category: str = "all",
    limit: int = 20,
    *,
    url: str = FEED_URL,
    transport: httpx.BaseTransport | None = None,
) -> list[NewsArticle]:
    if not 1 <= limit <= 50:
        raise ValueError("V0.2 fetch supports 1..50 items (pagination arrives in V0.3)")
    params: dict[str, str | int] = {
        "zhibo_id": 152, "tag_id": category_id(category),
        "page": 1, "page_size": limit, "pagesize": limit,
        "dire": "f", "dpc": 1, "type": 0,
    }
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://finance.sina.com.cn/7x24/",
    }
    try:
        with httpx.Client(
            timeout=httpx.Timeout(15.0),
            follow_redirects=False,
            headers=headers,
            transport=transport,
        ) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = parse_payload(response.text)
            return parse_feed(payload, datetime.now(UTC))
    except httpx.HTTPError as exc:
        raise SourceUnavailable("Sina request failed") from exc
