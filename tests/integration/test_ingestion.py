"""V0.3 integration tests: transport, full transactions, idempotency, recovery."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from news24.cli import main
from news24.core.errors import SourceSchemaError, SourceUnavailable
from news24.ingestion.service import run_ingestion
from news24.sources.sina.async_client import SinaFeedClient
from news24.storage.database import SQLiteNewsStore


def payload(ids: list[int], page: int, total: int, *, amended: bool = False) -> dict:
    records = []
    for item_id in ids:
        records.append({
            "id": item_id,
            "title": f"新闻{item_id}",
            "rich_text": f"<p>测试新闻{item_id}：宏观变化及经济数据</p>"
            + ("（已经更正）" if amended and item_id == 12 else ""),
            "create_time": f"2026-03-03 09:{item_id:02d}:00",
            "update_time": "2026-03-03 10:00:00" if amended and item_id == 12 else "",
            "is_delete": "1" if amended and item_id == 12 else "0",
            "tag": [{"name": "宏观"}],
            "ext": json.dumps({"stocks": [{"symbol": "600000", "key": "样本"}]}),
        })
    return {"result": {
        "status": {"code": 0},
        "data": {"feed": {
            "list": records, "page_info": {"page": page, "totalPage": total},
        }},
    }}


def mock_pages(
    pages: list[list[int]],
    *,
    amend: bool = False,
    fail_page: int | None = None,
    wrong_page: bool = False,
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        number = int(request.url.params["page"])
        if fail_page == number:
            return httpx.Response(503, json={"error": "unavailable"})
        ids = pages[number - 1] if number <= len(pages) else []
        data = payload(ids, number + int(wrong_page), len(pages), amended=amend)
        return httpx.Response(200, json=data)
    return httpx.MockTransport(handler)


async def ingest(
    store: SQLiteNewsStore,
    pages: list[list[int]],
    *,
    max_pages: int = 10,
    amend: bool = False,
    fail_page: int | None = None,
    category: str = "all",
    start: datetime | None = None,
    end: datetime | None = None,
    wrong_page: bool = False,
) -> dict:
    async with httpx.AsyncClient(transport=mock_pages(
        pages, amend=amend, fail_page=fail_page, wrong_page=wrong_page,
    )) as client:
        return await run_ingestion(
            store, SinaFeedClient(client, delay=0, retries=0),
            category=category, max_pages=max_pages, page_size=2,
            start=start, end=end,
        )


def test_migration_idempotent_and_wal(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "news.sqlite3") as store:
        assert store.migrate() == 2
        assert store.migrate() == 2
        assert store.conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert store.statistics()["news"] == 0
        assert store.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


@pytest.mark.asyncio
async def test_complete_ingest_roundtrip_search_and_raw_payload(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "news.sqlite3") as store:
        result = await ingest(store, [[12, 11], [10, 9]])
        assert result["status"] == "SUCCEEDED"
        assert result["inserted"] == 4 and result["pages"] == 2
        assert result["checkpoint"] == 12
        assert store.checkpoint("sina_7x24", "all") == 12
        assert store.statistics()["source_snapshots"] == 2
        assert store.statistics()["news_revisions"] == 4
        article = store.recent(1)[0]
        assert article.source_id == "12"
        assert article.raw["id"] == 12
        assert article.related_symbols == ["600000"]
        assert article.categories == ["宏观"]
        assert article.content_text.startswith("测试新闻")
        matches = store.search("经济数据")
        assert len(matches) == 4
        assert len(store.search("宏观")) == 4
        snapshot = store.conn.execute(
            "SELECT payload_json FROM source_snapshots LIMIT 1"
        ).fetchone()[0]
        assert json.loads(snapshot)["result"]["data"]["feed"]["list"]
        assert len(store.revisions("sina_7x24:12")) == 1


@pytest.mark.asyncio
async def test_idempotent_overlap_and_history_revision(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "news.sqlite3") as store:
        await ingest(store, [[12, 11]])
        repeat = await ingest(store, [[12, 11]])
        assert repeat["status"] == "NO_CHANGES"
        assert repeat["inserted"] == 0
        assert store.statistics()["news"] == 2
        assert store.statistics()["news_revisions"] == 2

        corrected = await ingest(store, [[12, 11]], amend=True)
        assert corrected["status"] == "SUCCEEDED"
        assert corrected["revised"] == 1
        assert store.statistics()["news"] == 2
        assert store.statistics()["news_revisions"] == 3
        assert store.recent(1)[0].is_deleted is True
        assert len(store.revisions("sina_7x24:12")) == 2
        assert "更正" in store.search("更正")[0].content_raw

        # Returning to the original source payload must create another revision.
        revert = await ingest(store, [[12, 11]], amend=False)
        assert revert["revised"] == 1
        assert len(store.revisions("sina_7x24:12")) == 3
        assert store.recent(1)[0].is_deleted is False


@pytest.mark.asyncio
async def test_page_limit_does_not_advance_checkpoint(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "news.sqlite3") as store:
        partial = await ingest(store, [[12, 11], [10, 9]], max_pages=1)
        assert partial["status"] == "INCOMPLETE"
        assert partial["checkpoint"] is None
        assert store.statistics()["news"] == 2
        assert store.checkpoint("sina_7x24", "all") is None
        complete = await ingest(store, [[12, 11], [10, 9]], max_pages=2)
        assert complete["inserted"] == 2
        assert complete["checkpoint"] == 12
        assert store.statistics()["news"] == 4


@pytest.mark.asyncio
async def test_source_failure_preserves_checkpoint_and_no_snapshots(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "news.sqlite3") as store:
        await ingest(store, [[12, 11]])
        with pytest.raises(SourceUnavailable):
            await ingest(store, [[14, 13], [12, 11]], fail_page=2)
        assert store.checkpoint("sina_7x24", "all") == 12
        assert store.statistics()["news"] == 2
        assert store.statistics()["source_snapshots"] == 1
        latest = store.conn.execute(
            "SELECT status FROM ingestion_runs ORDER BY started_at DESC, rowid DESC LIMIT 1"
        ).fetchone()[0]
        assert latest == "FAILED"


@pytest.mark.asyncio
async def test_transaction_rollback_failure_preserves_watermark(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "news.sqlite3") as store:
        store.migrate()
        store.conn.execute(
            "CREATE TRIGGER reject_news BEFORE INSERT ON news BEGIN "
            "SELECT RAISE(ABORT,'write failure'); END;"
        )
        with pytest.raises(sqlite3.IntegrityError):
            await ingest(store, [[12, 11]])
        assert store.statistics()["news"] == 0
        assert store.statistics()["source_snapshots"] == 0
        assert store.checkpoint("sina_7x24", "all") is None
        assert store.conn.execute(
            "SELECT status FROM ingestion_runs"
        ).fetchone()[0] == "FAILED"


@pytest.mark.asyncio
async def test_invalid_page_contract_fails_closed(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "news.sqlite3") as store:
        with pytest.raises(SourceSchemaError):
            await ingest(store, [[12, 11]], wrong_page=True)
        assert store.statistics()["news"] == 0
        assert store.checkpoint("sina_7x24", "all") is None


@pytest.mark.asyncio
async def test_backfill_does_not_move_realtime_checkpoint(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "news.sqlite3") as store:
        await ingest(store, [[12, 11]])
        start = datetime.fromisoformat("2026-03-03T09:11:00+08:00")
        end = datetime.fromisoformat("2026-03-03T09:13:00+08:00")
        result = await ingest(
            store, [[15, 14], [12, 11], [10, 9]], start=start, end=end
        )
        assert result["status"] == "NO_CHANGES"
        assert result["checkpoint"] == 12
        assert store.checkpoint("sina_7x24", "all") == 12
        assert store.statistics()["news"] == 2  # both 11 and 12 already existed


def test_interrupted_run_recovery(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "news.sqlite3") as store:
        store.migrate()
        store.begin_run("abandoned-run", "sina_7x24", "all")
        assert store.recover_interrupted() == 1
        assert store.recover_interrupted() == 0
        assert store.conn.execute(
            "SELECT status FROM ingestion_runs WHERE run_id='abandoned-run'"
        ).fetchone()[0] == "FAILED"
        assert store.checkpoint("sina_7x24", "all") is None


def test_db_cli_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = str(tmp_path / "news.sqlite3")
    assert main(["db", "migrate", "--db", db]) == 0
    assert main(["db", "stats", "--db", db]) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["news"] == 0
    assert main(["db", "search", "宏观", "--db", db]) == 0
    assert main(["db", "revisions", "sina_7x24:12", "--db", db]) == 0
    assert main(["db", "recover", "--db", db]) == 0
