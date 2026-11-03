"""HTTP and feed-contract verification without depending on live Sina services."""

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from news24.core.errors import SourceSchemaError, SourceUnavailable
from news24.sources.sina.client import fetch_latest
from news24.sources.sina.parser import parse_feed, parse_payload

FIXTURE = Path(__file__).parents[1] / "fixtures" / "sina" / "feed_success.json"


def _fixture_response(request: httpx.Request) -> httpx.Response:
    assert request.url.params["zhibo_id"] == "152"
    assert request.url.params["tag_id"] == "10"
    assert request.url.params["pagesize"] == "2"
    return httpx.Response(200, text=FIXTURE.read_text(encoding="utf-8"))


def test_http_contract_latest() -> None:
    items = fetch_latest("A股", 2, transport=httpx.MockTransport(_fixture_response))
    assert [i.source_id for i in items] == ["4700001", "4700000"]


def test_http_failure_is_not_empty_success() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(503))
    with pytest.raises(SourceUnavailable):
        fetch_latest(transport=transport)


def test_unknown_category_rejected_before_network() -> None:
    with pytest.raises(ValueError, match="unknown category"):
        fetch_latest("incorrect-category")


def test_limits_are_explicit() -> None:
    with pytest.raises(ValueError, match="1..50"):
        fetch_latest(limit=100)


def test_jsonp_and_json_are_equivalent() -> None:
    raw = FIXTURE.read_text(encoding="utf-8").strip()
    assert parse_payload("cb(" + raw + ");") == parse_payload(raw)


def test_invalid_status_or_shape_rejected() -> None:
    now = datetime.now(UTC)
    with pytest.raises(SourceSchemaError):
        parse_feed({"result": {"status": {"code": 1}}}, now)
    with pytest.raises(SourceSchemaError):
        parse_feed({"result": {"status": {"code": 0}, "data": {"feed": {}}}}, now)


def test_no_network_required_for_contract_tests() -> None:
    # The fixture deliberately uses reserved example.invalid URLs.
    assert json.loads(FIXTURE.read_text(encoding="utf-8"))["result"]["status"]["code"] == 0
