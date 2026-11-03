"""V1.0 integrated audit: read API, optimistic operator review, and CLI quality gates."""

import asyncio
import hashlib
import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from http.server import ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest

from news24.cli import main
from news24.core.models import NewsArticle
from news24.evaluation.quality import evaluate_evidence, readiness
from news24.ingestion.models import FetchBatch
from news24.intelligence.models import AnalysisCandidate, AnalysisSpec, ModelReply
from news24.intelligence.service import analyze_article
from news24.review.service import (
    claim_reviews,
    event_reviews,
    review_claim,
    review_event,
)
from news24.storage.database import SQLiteNewsStore
from news24.web.server import make_handler, read_news, serve

NOW = datetime(2026, 11, 3, 0, 0, tzinfo=UTC)
QUOTE = "本公司宣布在上海建设新的数据研发中心"
TOKEN = "this-is-a-local-review-token-only"


class FakeProvider:
    async def analyze(
        self, title: str | None, content: str, spec: AnalysisSpec
    ) -> ModelReply:
        return ModelReply(data=AnalysisCandidate.model_validate({
            "sentiment": "neutral",
            "claims": [{"statement": "公司公布研发建设计划", "quote": QUOTE}],
        }))


def seed(store: SQLiteNewsStore, *, key: int, text: str) -> str:
    uid = f"sina_7x24:{key}"
    article = NewsArticle(
        uid=uid, source="sina_7x24", source_id=str(key), title="新闻<待证>",
        content_raw=text, content_text=text,
        published_at=datetime.fromisoformat("2026-11-02T10:00:00+08:00"),
        fetched_at=NOW,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        raw={"id": key, "body": text},
    )
    store.migrate()
    store.begin_run(f"seed-{key}-{hashlib.md5(text.encode()).hexdigest()[:8]}",
                    "sina_7x24", "all")
    store.apply_batch(
        f"seed-{key}-{hashlib.md5(text.encode()).hexdigest()[:8]}",
        "sina_7x24", "all",
        FetchBatch(articles=[article],complete=True,reason="test"),
    )
    return uid


def populate(db: Path) -> tuple[str, str, str]:
    with SQLiteNewsStore(db) as store:
        uid = seed(store, key=77, text="快讯：" + QUOTE + "。")
        analysis = asyncio.run(analyze_article(
            store,uid,AnalysisSpec(provider="fixture",model="offline-model"),
            FakeProvider(),now=NOW,
        ))
        event = store.conn.execute(
            "SELECT event_key FROM event_clusters LIMIT 1"
        ).fetchone()[0]
        return uid, str(analysis["analysis_key"]), str(event)


@contextmanager
def running(db: Path, *, token: str | None = TOKEN) -> Iterator[tuple[str, httpx.Client]]:
    handler = make_handler(db, review_token=token)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}"
        with httpx.Client(base_url=url, timeout=5) as client:
            yield url, client
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_upgrade_v3_to_v4_preserves_news_and_analysis(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite3"
    from importlib import resources

    package = resources.files("news24.storage.migrations")
    sql = "\n".join(
        package.joinpath(f"000{i}_{name}.sql").read_text(encoding="utf-8")
        for i,name in (
            (1,"initial"),(2,"jobs"),(3,"intelligence"),
        )
    )
    with sqlite3.connect(path) as connection:
        connection.executescript(sql+"\nPRAGMA user_version=3;")
        connection.execute(
            """INSERT INTO job_queue
               (job_key,kind,payload_json,state,max_attempts,available_at,
                created_at,updated_at)
               VALUES ('old-job','report','{}','QUEUED',3,?,?,?)""",
            (NOW.isoformat(),NOW.isoformat(),NOW.isoformat()),
        )
        connection.commit()
    with SQLiteNewsStore(path) as store:
        assert store.migrate() == 4
        assert store.migrate() == 4
        assert store.conn.execute(
            "SELECT COUNT(*) FROM job_queue WHERE job_key='old-job'"
        ).fetchone()[0] == 1
        assert store.conn.execute(
            "SELECT name FROM sqlite_master WHERE name='claim_review_log'"
        ).fetchone()[0] == "claim_review_log"


def test_claim_audit_append_only_conflict_and_revision_fence(tmp_path: Path) -> None:
    db=tmp_path/"data.sqlite3"
    uid,key,_=populate(db)
    with SQLiteNewsStore(db) as store:
        rev=store.conn.execute(
            "SELECT revision_hash FROM news WHERE uid=?",(uid,)
        ).fetchone()[0]
        first=review_claim(
            store,analysis_key=key,claim_index=0,
            expected_version=0,expected_source_revision=rev,
            decision="SUPPORTED_BY_TEXT",
            reason="该原文具有完整且唯一的引用区间",
            reviewer="tester",
        )
        assert first["review_version"]==1
        with pytest.raises(ValueError,match="version conflict"):
            review_claim(
                store,analysis_key=key,claim_index=0,
                expected_version=0,expected_source_revision=rev,
                decision="NOT_SUPPORTED_BY_TEXT",reason="另外的人工判断理由",
                reviewer="tester",
            )
        second=review_claim(
            store,analysis_key=key,claim_index=0,
            expected_version=1,expected_source_revision=rev,
            decision="NEEDS_INVESTIGATION",reason="需要另一个独立来源复核",
            reviewer="tester",
        )
        assert second["review_version"]==2
        assert store.conn.execute(
            "SELECT COUNT(*) FROM claim_review_log"
        ).fetchone()[0] == 2
        assert claim_reviews(store,key)[0]["review_version"] == 2

        seed(store,key=77,text="更正消息，真实情况暂不确定。")
        with pytest.raises(ValueError,match="stale"):
            review_claim(
                store,analysis_key=key,claim_index=0,
                expected_version=2,expected_source_revision=rev,
                decision="NEEDS_INVESTIGATION",reason="不应该批准已经修改的旧新闻内容",
                reviewer="tester",
            )


def test_review_rejects_short_reasons_and_unknown_claim(tmp_path: Path) -> None:
    db=tmp_path/"news.sqlite3"
    uid,key,_=populate(db)
    with SQLiteNewsStore(db) as store:
        rev=store.conn.execute("SELECT revision_hash FROM news WHERE uid=?",(uid,)).fetchone()[0]
        with pytest.raises(ValueError,match="8..1000"):
            review_claim(store,analysis_key=key,claim_index=0,expected_version=0,
                expected_source_revision=rev,decision="NEEDS_INVESTIGATION",
                reason="短",reviewer="tester")
        with pytest.raises(ValueError,match="unknown"):
            review_claim(store,analysis_key=key,claim_index=99,expected_version=0,
                expected_source_revision=rev,decision="NEEDS_INVESTIGATION",
                reason="该索引不存在于当前分析中",reviewer="tester")


def test_event_review_optimistic_history(tmp_path: Path) -> None:
    db=tmp_path/"data.sqlite3"
    _,_,event=populate(db)
    with SQLiteNewsStore(db) as store:
        first=review_event(
            store,event_key=event,expected_version=0,decision="RELATED",
            reason="仅表示两条候选文本可能相关",reviewer="operator",
        )
        assert first["review_version"]==1
        with pytest.raises(ValueError,match="conflict"):
            review_event(
                store,event_key=event,expected_version=0,decision="NOT_RELATED",
                reason="不允许重复提交旧版本审核",reviewer="operator",
            )
        assert event_reviews(store,event)[0]["verdict"] == "RELATED"


def test_http_public_read_escapes_query_and_contains_evidence(tmp_path: Path) -> None:
    db=tmp_path/"data.sqlite3"
    uid,key,event=populate(db)
    with running(db) as (_,client):
        page=client.get("/")
        assert page.status_code==200 and b"app.js" in page.content
        assert "default-src 'none'" in page.headers["Content-Security-Policy"]
        js=client.get("/app.js")
        assert js.status_code==200 and "textContent" in js.text
        assert "innerHTML =" not in js.text
        assert client.get("/api/news").json()["total"] == 1
        assert client.get("/api/news",params={"q":"新闻<待证>"}).json()["total"] == 1
        assert client.get("/api/news",params={"q":"%"}).json()["total"] == 0
        detail=client.get("/api/article",params={"uid":uid})
        assert detail.status_code==200 and detail.json()["content_text"].endswith("。")
        assert client.get("/api/analyses",params={"uid":uid}).json()["items"]
        evidence=client.get("/api/evidence",params={"key":key}).json()
        assert evidence["items"][0]["verdict"]=="TEXT_MATCH_ONLY"
        assert client.get("/api/events").json()["items"]
        assert client.get("/api/event",params={"key":event}).json()["members"]
        assert client.get("/api/jobs").status_code==200
        assert client.get("/api/health").json()["schema_version"]==4
        assert client.get("/api/evaluations").json()["items"]==[]


def test_http_host_validation_and_query_limits(tmp_path: Path) -> None:
    db=tmp_path/"data.sqlite3"
    populate(db)
    with running(db) as (_,client):
        assert client.get("/api/news",headers={"Host":"evil.test"}).status_code==403
        assert client.get("/api/news",params={"limit":"9999"}).status_code==422
        assert client.get("/api/news",params={"q":["x","y"]}).status_code==422
        assert client.get("/api/article",params={"uid":"missing"}).status_code==404
        assert client.get("/not-a-route").status_code==404


def test_http_review_auth_csrf_and_version_conflict(tmp_path: Path) -> None:
    db=tmp_path/"data.sqlite3"
    uid,key,event=populate(db)
    with SQLiteNewsStore(db) as store:
        rev=store.conn.execute("SELECT revision_hash FROM news WHERE uid=?",(uid,)).fetchone()[0]
    payload={
        "analysis_key":key,"claim_index":0,"expected_source_revision":rev,
        "expected_version":0,"decision":"SUPPORTED_BY_TEXT",
        "reason":"文本引文确实存在且对应当前新闻修订",
    }
    with running(db) as (base,client):
        url="/api/reviews/claim"
        assert client.post(url,json=payload).status_code==403
        headers={"Origin":base}
        assert client.post(url,json=payload,headers=headers).status_code==401
        headers["Authorization"]="Bearer wrong"
        assert client.post(url,json=payload,headers=headers).status_code==401
        headers["Authorization"]="Bearer "+TOKEN
        ok=client.post(url,json=payload,headers=headers)
        assert ok.status_code==201
        assert ok.json()["review_version"]==1
        assert TOKEN not in ok.text
        assert client.post(url,json=payload,headers=headers).status_code==409
        assert client.get("/api/evidence",params={"key":key}).json()["reviews"][0]["review_version"]==1
        e={"event_key":event,"expected_version":0,"decision":"RELATED",
           "reason":"候选条目有共同原文但仍需核验"}
        assert client.post("/api/reviews/event",json=e,headers=headers).status_code==201


def test_http_no_write_when_unconfigured(tmp_path: Path) -> None:
    db=tmp_path/"data.sqlite3"
    _,key,_=populate(db)
    with running(db,token=None) as (base,client):
        h={"Origin":base,"Authorization":"Bearer "+TOKEN}
        assert client.post("/api/reviews/claim",headers=h,json={
            "analysis_key":key,
        }).status_code==403


def test_server_refuses_nonloopback(tmp_path: Path) -> None:
    with pytest.raises(ValueError,match="127.0.0.1"):
        serve(tmp_path/"data.sqlite3",host="0.0.0.0",port=8765)
    with pytest.raises(ValueError,match="16 characters"):
        make_handler(tmp_path/"data.sqlite3",review_token="short")


def test_evaluation_results_are_idempotent_and_not_truth_claims(tmp_path: Path) -> None:
    db=tmp_path/"data.sqlite3"
    fixture=Path(__file__).parents[1]/"fixtures"/"intelligence"/"evidence_gold.json"
    with SQLiteNewsStore(db) as store:
        first=evaluate_evidence(store,fixture)
        second=evaluate_evidence(store,fixture)
        assert first["ok"] and first["cases"]>=7
        assert second["run_id"]==first["run_id"]
        assert store.conn.execute(
            "SELECT COUNT(*) FROM evaluation_runs"
        ).fetchone()[0] == 1
        assert readiness(store)["readiness"]=="NOT_PRODUCTION_VERIFIED"
    assert main(["evaluate","evidence","--dataset",str(fixture),"--db",str(db)])==0
    assert main(["audit","--db",str(db)])==0


def test_evaluation_nonmatching_gold_returns_nonzero(tmp_path: Path) -> None:
    dataset=tmp_path/"gold.json"
    dataset.write_text(json.dumps({"cases":[{
      "text":"完全不同的文本","quote":"不存在的主张","verdict":"TEXT_MATCH_ONLY",
    }]}),encoding="utf-8")
    assert main(["evaluate","evidence","--dataset",str(dataset),
                 "--db",str(tmp_path/"data.db")])==3


def test_news_pagination_and_search_bounds(tmp_path: Path) -> None:
    with SQLiteNewsStore(tmp_path/"data.db") as store:
        for i in range(3):
            seed(store,key=i+1,text="新闻正文"+str(i))
        response=read_news(store,limit=2,offset=0)
        assert response["total"]==3
        assert len(response["items"])==2
        assert response["next_offset"]==2
        other=read_news(store,limit=2,offset=2)
        assert len(other["items"])==1
        assert other["next_offset"] is None
        with pytest.raises(ValueError):
            read_news(store,limit=101)
