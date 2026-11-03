"""V0.5: provenance, rejection, dedupe, event candidates and worker contract."""

import hashlib
import sqlite3
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

import pytest

from news24.cli import main
from news24.core.models import NewsArticle
from news24.ingestion.models import FetchBatch
from news24.intelligence.models import AnalysisCandidate, AnalysisSpec, ModelReply
from news24.intelligence.provider import OpenAIResponsesProvider
from news24.intelligence.service import (
    analysis_history,
    analyze_article,
    event_candidates,
    evidence_for,
)
from news24.jobs.store import JobStore
from news24.jobs.worker import JobWorker
from news24.storage.database import SQLiteNewsStore

NOW = datetime(2026, 11, 3, tzinfo=UTC)
QUOTE = "某公司宣布在上海新建先进研发中心"


class FakeProvider:
    def __init__(
        self,
        *,
        quote: str = QUOTE,
        statement: str = "某公司宣布新建研发中心",
        sentiment: str = "neutral",
    ) -> None:
        self.quote = quote
        self.statement = statement
        self.sentiment = sentiment
        self.calls = 0

    async def analyze(self, title: str | None, content: str, spec: AnalysisSpec) -> ModelReply:
        self.calls += 1
        return ModelReply(
            data=AnalysisCandidate.model_validate({
                "sentiment": self.sentiment,
                "claims": [{"quote": self.quote, "statement": self.statement}],
            }),
            response_id=f"fixture-{self.calls}",
            input_tokens=50, output_tokens=20,
        )


def article(uid: int, text: str) -> NewsArticle:
    return NewsArticle(
        uid=f"sina_7x24:{uid}",
        source="sina_7x24", source_id=str(uid),
        title="样本快讯", content_raw=text, content_text=text,
        published_at=datetime.fromisoformat("2026-11-02T12:30:00+08:00"),
        fetched_at=NOW, content_hash=hashlib.sha256(text.encode()).hexdigest(),
        raw={"id": uid, "text": text},
    )


def add(store: SQLiteNewsStore, run: str, rows: list[NewsArticle]) -> None:
    store.migrate()
    store.begin_run(run, "sina_7x24", "all")
    store.apply_batch(run, "sina_7x24", "all", FetchBatch(
        articles=rows, complete=True, reason="fixture", checkpoint_after=None,
    ))


def spec(model: str = "test-model") -> AnalysisSpec:
    return AnalysisSpec(provider="fixture", model=model)


def test_schema_v2_upgrade_preserves_job_queue(tmp_path: Path) -> None:
    db = tmp_path / "data.db"
    migrations = resources.files("news24.storage.migrations")
    v1 = migrations.joinpath("0001_initial.sql").read_text(encoding="utf-8")
    v2 = migrations.joinpath("0002_jobs.sql").read_text(encoding="utf-8")
    with sqlite3.connect(db) as connection:
        connection.executescript(v1 + "\n" + v2 + "\nPRAGMA user_version=2;")
        connection.execute(
            """INSERT INTO job_queue
               (job_key,kind,payload_json,state,max_attempts,available_at,
                created_at,updated_at)
               VALUES ('original-job','report','{}','QUEUED',3,?,?,?)""",
            (NOW.isoformat(), NOW.isoformat(), NOW.isoformat()),
        )
        connection.commit()
    with SQLiteNewsStore(db) as store:
        assert store.conn.execute("PRAGMA user_version").fetchone()[0] == 2
        assert store.migrate() == 4
        assert store.migrate() == 4
        assert JobStore(store).get("original-job") is not None
        assert store.conn.execute(
            "SELECT name FROM sqlite_master WHERE name='analysis_results'"
        ).fetchone() is not None


@pytest.mark.asyncio
async def test_verbatim_spans_and_cached_model_runs(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "db.sqlite3") as store:
        text = "公告：" + QUOTE + "，将推进研发。"
        add(store, "first", [article(1, text)])
        provider = FakeProvider()
        first = await analyze_article(store, "sina_7x24:1", spec(), provider, now=NOW)
        assert first["status"] == "ACCEPTED"
        assert first["text_matched"] == 1 and not first["cached"]
        ev = evidence_for(store, first["analysis_key"])
        assert ev[0]["verdict"] == "TEXT_MATCH_ONLY"
        assert text[ev[0]["span_start"]:ev[0]["span_end"]] == QUOTE
        again = await analyze_article(store, "sina_7x24:1", spec(), provider, now=NOW)
        assert again["cached"] and provider.calls == 1
        assert len(analysis_history(store, "sina_7x24:1")) == 1
        assert event_candidates(store, day="2026-11-02")[0]["distinct_articles"] == 1


@pytest.mark.asyncio
async def test_absent_quote_rejected_and_not_neutral(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "data.db") as store:
        add(store, "run", [article(1, "完全不同的资讯")])
        result = await analyze_article(store, "sina_7x24:1", spec(), FakeProvider(), now=NOW)
        assert result["status"] == "REJECTED" and result["sentiment"] is None
        rows = evidence_for(store, result["analysis_key"])
        assert rows[0]["verdict"] == "NOT_FOUND"
        assert rows[0]["span_start"] is None
        assert not event_candidates(store)
        recorded = store.conn.execute(
            "SELECT sentiment FROM analysis_results"
        ).fetchone()[0]
        assert recorded is None


@pytest.mark.asyncio
async def test_partial_results_are_not_claimed_as_verified(tmp_path: Path) -> None:
    class MixedProvider(FakeProvider):
        async def analyze(
            self, title: str | None, content: str, model_spec: AnalysisSpec
        ) -> ModelReply:
            return ModelReply(data=AnalysisCandidate.model_validate({
                "sentiment": "neutral",
                "claims": [
                    {"statement": "原文存在第一条内容", "quote": QUOTE},
                    {"statement": "原文说了不存在的事情", "quote": "原文中不存在这段报道"},
                ],
            }))

    with SQLiteNewsStore(tmp_path / "data.db") as store:
        add(store, "run", [article(1, "公告：" + QUOTE)])
        result = await analyze_article(store, "sina_7x24:1", spec(), MixedProvider())
        assert result["status"] == "PARTIAL" and result["text_matched"] == 1
        evidence = evidence_for(store, result["analysis_key"])
        assert [row["verdict"] for row in evidence] == [
            "TEXT_MATCH_ONLY", "NOT_FOUND",
        ]
        assert len(event_candidates(store)) == 1


@pytest.mark.asyncio
async def test_duplicate_quote_ambiguous_not_event(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "data.db") as store:
        add(store, "run", [article(1, QUOTE + "，" + QUOTE)])
        result = await analyze_article(store, "sina_7x24:1", spec(), FakeProvider())
        assert result["status"] == "REJECTED"
        assert evidence_for(store, result["analysis_key"])[0]["verdict"] == "AMBIGUOUS"
        assert event_candidates(store) == []


@pytest.mark.asyncio
async def test_same_quote_two_articles_only_candidate(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "data.db") as store:
        add(store, "run", [article(1, "甲：" + QUOTE), article(2, "乙：" + QUOTE)])
        for uid in (1, 2):
            await analyze_article(store, f"sina_7x24:{uid}", spec(), FakeProvider())
        events = event_candidates(store, day="2026-11-02")
        assert len(events) == 1
        assert events[0]["status"] == "CANDIDATE"
        assert events[0]["distinct_articles"] == 2


@pytest.mark.asyncio
async def test_model_version_creates_distinct_analysis(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "data.db") as store:
        add(store, "run", [article(1, QUOTE)])
        one = await analyze_article(store, "sina_7x24:1", spec("one"), FakeProvider())
        two = await analyze_article(store, "sina_7x24:1", spec("two"), FakeProvider())
        assert one["analysis_key"] != two["analysis_key"]
        assert len(analysis_history(store, "sina_7x24:1")) == 2


@pytest.mark.asyncio
async def test_old_revision_event_not_counted(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "data.db") as store:
        add(store, "first", [article(1, QUOTE)])
        await analyze_article(store, "sina_7x24:1", spec(), FakeProvider())
        assert len(event_candidates(store)) == 1
        add(store, "correction", [article(1, "该报道已经更正，具体信息待核实。")])
        assert event_candidates(store) == []
        failed = await analyze_article(store, "sina_7x24:1", spec(), FakeProvider())
        assert failed["status"] == "REJECTED"
        assert len(analysis_history(store, "sina_7x24:1")) == 2


@pytest.mark.asyncio
async def test_stale_revision_fences_model_completion(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "data.db") as store:
        add(store, "initial", [article(1, QUOTE)])

        class MutatingProvider(FakeProvider):
            async def analyze(
                self, title: str | None, content: str, model_spec: AnalysisSpec
            ) -> ModelReply:
                add(store, "changed", [article(1, "修订新闻：" + QUOTE)])
                return await super().analyze(title, content, model_spec)

        with pytest.raises(RuntimeError, match="article changed"):
            await analyze_article(store, "sina_7x24:1", spec(), MutatingProvider())
        assert store.conn.execute("SELECT COUNT(*) FROM analysis_results").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_analysis_evidence_transaction_rolls_back(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "data.db") as store:
        add(store, "initial", [article(1, QUOTE)])
        store.conn.execute(
            "CREATE TRIGGER reject_evidence BEFORE INSERT ON evidence_spans "
            "BEGIN SELECT RAISE(ABORT,'reject'); END;"
        )
        with pytest.raises(sqlite3.IntegrityError):
            await analyze_article(store, "sina_7x24:1", spec(), FakeProvider())
        assert store.conn.execute("SELECT COUNT(*) FROM analysis_results").fetchone()[0] == 0
        assert store.conn.execute("SELECT COUNT(*) FROM event_clusters").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_worker_analyze_handler_uses_provider_and_records(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "data.db") as store:
        add(store, "initial", [article(1, QUOTE)])
        jobs = JobStore(store)
        jobs.enqueue(
            "model:1", "analyze",
            {"uid": "sina_7x24:1", "provider": "fixture", "model": "test-model"},
            now=NOW,
        )
        worker = JobWorker(store, analysis_provider=FakeProvider(), clock=lambda: NOW)
        result = await worker.run_once()
        assert result["state"] == "SUCCEEDED"
        assert result["result"]["status"] == "ACCEPTED"
        assert jobs.get("model:1")["state"] == "SUCCEEDED"


@pytest.mark.asyncio
async def test_worker_rejected_analysis_retries_not_success(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path / "data.db") as store:
        add(store, "initial", [article(1, "与证据完全不同的新闻")])
        JobStore(store).enqueue(
            "model:reject", "analyze",
            {"uid": "sina_7x24:1", "provider": "fixture", "model": "fixture"},
            now=NOW, max_attempts=1,
        )
        worker = JobWorker(store, analysis_provider=FakeProvider(), clock=lambda: NOW)
        result = await worker.run_once()
        assert result["state"] == "FAILED"
        assert len(analysis_history(store, "sina_7x24:1")) == 1


@pytest.mark.asyncio
async def test_missing_credentials_never_synthesizes_neutral(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAIResponsesProvider()
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await provider.analyze(None, "新闻正文", AnalysisSpec(provider="openai", model="x"))


def test_intelligence_cli_is_offline_and_auditable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = str(tmp_path / "data.db")
    with SQLiteNewsStore(db) as store:
        add(store, "initial", [article(1, QUOTE)])
    assert main([
        "intelligence", "enqueue", "--uid", "sina_7x24:1",
        "--model", "test-model", "--db", db,
    ]) == 0
    assert main([
        "intelligence", "enqueue", "--uid", "sina_7x24:1",
        "--model", "test-model", "--db", db,
    ]) == 0
    assert main([
        "intelligence", "history", "--uid", "sina_7x24:1", "--db", db,
    ]) == 0
    assert main(["intelligence", "events", "--db", db]) == 0
    assert main(["intelligence", "evidence", "--key", "missing", "--db", db]) == 0
    with SQLiteNewsStore(db) as store:
        assert JobStore(store).counts() == {"QUEUED": 1}
    assert "enqueued" in capsys.readouterr().out
