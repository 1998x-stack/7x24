"""Explicit page and ingestion-result contracts."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from news24.domain.news import NewsArticle


@dataclass(frozen=True)
class FeedPage:
    number: int
    fetched_at: datetime
    articles: list[NewsArticle]
    raw: dict[str, Any]
    total_pages: int | None


@dataclass
class FetchBatch:
    pages: list[FeedPage] = field(default_factory=list)
    articles: list[NewsArticle] = field(default_factory=list)
    complete: bool = False
    checkpoint_before: int | None = None
    checkpoint_after: int | None = None
    reason: str = "page_limit"

    @property
    def pages_fetched(self) -> int:
        return len(self.pages)
