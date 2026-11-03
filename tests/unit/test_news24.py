"""Pure offline tests of canonical modeling and safe export."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from news24.cli import main
from news24.core.models import NewsArticle
from news24.sources.sina.parser import parse_feed, parse_payload, visible_text

FIXTURE = Path(__file__).parents[1] / "fixtures" / "sina" / "feed_success.json"


def _articles() -> list[NewsArticle]:
    return parse_feed(
        parse_payload(FIXTURE.read_text(encoding="utf-8")),
        datetime(2026, 3, 3, 2, tzinfo=UTC),
    )


def test_article_fields_survive_parsing() -> None:
    items = _articles()
    assert len(items) == 2
    item = items[0]
    assert item.uid == "sina_7x24:4700001"
    assert item.title == "测试快讯标题"
    assert item.content_raw.startswith("<p>")
    assert item.content_text == "测试：A股市场成交变化。"
    assert item.related_symbols == ["600000"]
    assert item.categories == ["A股", "市场"]
    assert item.published_at is not None
    assert item.published_at.isoformat() == "2026-03-03T09:30:00+08:00"
    assert item.raw["multimedia"] == {"img_url": ["https://example.invalid/image.png"]}
    assert len(item.content_hash) == 64


def test_deleted_flag_does_not_confuse_string_zero() -> None:
    payload = parse_payload(FIXTURE.read_text(encoding="utf-8"))
    payload["result"]["data"]["feed"]["list"][0]["is_delete"] = "0"
    kept = parse_feed(payload, datetime(2026, 3, 3, tzinfo=UTC))
    assert kept[0].is_deleted is False
    payload["result"]["data"]["feed"]["list"][0]["is_delete"] = "1"
    deleted = parse_feed(payload, datetime(2026, 3, 3, tzinfo=UTC))
    assert deleted[0].is_deleted is True


def test_invalid_publish_time_never_becomes_now() -> None:
    assert _articles()[1].published_at is None


def test_timestamps_reject_naive() -> None:
    data = _articles()[0].model_dump()
    data["fetched_at"] = datetime(2026, 3, 3)
    with pytest.raises(ValidationError, match="timezone-aware"):
        NewsArticle.model_validate(data)


def test_text_extraction_excludes_scripts() -> None:
    assert visible_text("<p>安全<script>alert(1)</script>文本</p>") == "安全文本"


def test_cli_fixture_check(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["test-fixtures", str(FIXTURE)]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 2


def test_cli_inspect_and_overwrite_guard(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from news24.cli import _atomic_jsonl

    output = tmp_path / "subdir" / "news.jsonl"
    _atomic_jsonl(output, _articles(), False)
    assert main(["inspect", str(output), "--limit", "1"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows["count"] == 1
    assert rows["items"][0]["uid"] == "sina_7x24:4700000"
    with pytest.raises(FileExistsError):
        _atomic_jsonl(output, _articles(), False)
    _atomic_jsonl(output, _articles(), True)
    assert len(output.read_text(encoding="utf-8").splitlines()) == 2


def test_cli_invalid_limit_returns_parser_error() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["inspect", "fake.jsonl", "--limit", "0"])
    assert exc.value.code == 2
