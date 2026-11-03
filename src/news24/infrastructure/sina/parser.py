"""No-loss feed parsing with visible text as a derived representation."""

import hashlib
import html
import json
import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Any
from zoneinfo import ZoneInfo

from news24.domain.errors import SourceSchemaError
from news24.domain.news import NewsArticle

_SHANGHAI = ZoneInfo("Asia/Shanghai")
_JSONP = re.compile(r"^[A-Za-z_$][\w.$]*\s*\((.*)\)\s*;?\s*$", re.DOTALL)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.suppressed = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self.suppressed += 1
        if tag in ("p", "div", "br", "li"):
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self.suppressed:
            self.suppressed -= 1
        if tag in ("p", "div", "li"):
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.suppressed:
            self.parts.append(data)


def visible_text(raw: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(raw)
    return " ".join(html.unescape("".join(extractor.parts)).split())


def parse_payload(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped.startswith("{"):
        match = _JSONP.fullmatch(stripped)
        if match is None:
            raise SourceSchemaError("invalid JSON or JSONP wrapper")
        stripped = match.group(1)
    try:
        result = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise SourceSchemaError("malformed JSON payload") from exc
    if not isinstance(result, dict):
        raise SourceSchemaError("expected an object")
    return result


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return parsed.replace(tzinfo=_SHANGHAI)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            result = json.loads(value)
            return result if isinstance(result, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def parse_feed(payload: dict[str, Any], fetched_at: datetime) -> list[NewsArticle]:
    if fetched_at.utcoffset() is None:
        raise ValueError("fetched_at must carry a timezone")
    try:
        result = payload["result"]
        status = result["status"]
        if status["code"] != 0:
            raise SourceSchemaError(f"source returned status {status['code']}")
        items = result["data"]["feed"]["list"]
    except (KeyError, TypeError, IndexError) as exc:
        raise SourceSchemaError("unexpected Sina feed shape") from exc
    if not isinstance(items, list):
        raise SourceSchemaError("feed.list must be an array")
    parsed: list[NewsArticle] = []
    for raw in items:
        if not isinstance(raw, dict) or raw.get("id") is None:
            raise SourceSchemaError("news item missing id")
        source_id = str(raw["id"])
        content = raw.get("rich_text") or ""
        if not isinstance(content, str):
            raise SourceSchemaError(f"non-text rich_text for {source_id}")
        ext = _as_dict(raw.get("ext"))
        tags = raw.get("tag") or []
        if not isinstance(tags, list):
            raise SourceSchemaError(f"invalid tag list for {source_id}")
        symbols = [
            str(stock.get("symbol"))
            for stock in ext.get("stocks", [])
            if isinstance(stock, dict) and stock.get("symbol")
        ] if isinstance(ext.get("stocks", []), list) else []
        tag_names = [
            str(t["name"]) for t in tags
            if isinstance(t, dict) and t.get("name")
        ]
        parsed.append(NewsArticle(
            uid=f"sina_7x24:{source_id}",
            source="sina_7x24",
            source_id=source_id,
            title=raw.get("title") or None,
            content_raw=content,
            content_text=visible_text(content),
            published_at=_parse_time(raw.get("create_time")),
            updated_at=_parse_time(raw.get("update_time")),
            fetched_at=fetched_at,
            source_url=ext.get("docurl") or raw.get("docurl") or None,
            categories=tag_names,
            tags=tag_names,
            related_symbols=symbols,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            is_deleted=str(raw.get("is_delete", "0")).lower() in ("1", "true"),
            is_repeated=str(raw.get("is_repeat", "0")) == "1",
            raw=raw,
        ))
    return parsed
