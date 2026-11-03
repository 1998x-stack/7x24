"""Versioned canonical article model; retain original source payload."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NewsArticle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uid: str
    source: str
    source_id: str
    title: str | None = None
    content_raw: str
    content_text: str
    published_at: datetime | None
    updated_at: datetime | None = None
    fetched_at: datetime
    source_url: str | None = None
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    related_symbols: list[str] = Field(default_factory=list)
    content_hash: str
    is_deleted: bool = False
    is_repeated: bool = False
    raw: dict[str, object] = Field(default_factory=dict)

    @field_validator("published_at", "updated_at", "fetched_at")
    @classmethod
    def timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return value
