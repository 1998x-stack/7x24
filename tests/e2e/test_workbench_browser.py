"""Real Chromium interaction test for the local review workbench.

This test is run in a dedicated GitHub Actions browser job and never calls an
external source or a real LLM. Source markup must remain inert text.
"""

import asyncio
import hashlib
import threading
from datetime import UTC, datetime
from http.server import ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

from news24.core.models import NewsArticle
from news24.ingestion.models import FetchBatch
from news24.intelligence.models import AnalysisCandidate, AnalysisSpec, ModelReply
from news24.intelligence.service import analyze_article
from news24.storage.database import SQLiteNewsStore
from news24.web.server import make_handler

TOKEN = "v1-local-test-token-with-good-length"
QUOTE = "本公司宣布在上海建设新的数据研发中心"
NOW = datetime(2026, 11, 3, tzinfo=UTC)


class FixtureProvider:
    async def analyze(
        self, title: str | None, content: str, spec: AnalysisSpec
    ) -> ModelReply:
        return ModelReply(data=AnalysisCandidate.model_validate({
            "sentiment": "unknown",
            "claims": [{"statement": "公告涉及研发中心", "quote": QUOTE}],
        }))


def setup(db: Path) -> None:
    with SQLiteNewsStore(db) as store:
        store.migrate()
        article=NewsArticle(
            uid="sina_7x24:123",
            source="sina_7x24", source_id="123",
            title="资讯<img src=x onerror=alert(1)>",
            content_raw="<p>"+QUOTE+"</p>",
            content_text="公告："+QUOTE+"。", published_at=NOW,
            fetched_at=NOW, content_hash=hashlib.sha256(QUOTE.encode()).hexdigest(),
            raw={"id":123},
        )
        store.begin_run("seed-browser","sina_7x24","all")
        store.apply_batch(
            "seed-browser","sina_7x24","all",
            FetchBatch(articles=[article],complete=True,reason="test"),
        )
        asyncio.run(analyze_article(
            store,"sina_7x24:123",
            AnalysisSpec(provider="fixture",model="golden"),
            FixtureProvider(),now=NOW,
        ))


def test_browser_news_evidence_review_and_mobile(tmp_path: Path) -> None:
    db=tmp_path/"browser.sqlite3"
    setup(db)
    server=ThreadingHTTPServer(
        ("127.0.0.1",0),make_handler(db,review_token=TOKEN)
    )
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    url=f"http://127.0.0.1:{server.server_address[1]}"
    errors: list[str]=[]
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True)
            page=browser.new_page(viewport={"width":1280,"height":800})
            page.on("pageerror",lambda error: errors.append(str(error)))
            page.goto(url,wait_until="networkidle")
            page.get_by_text("资讯<img",exact=False).first.wait_for()
            assert page.locator('img[src="x"]').count()==0
            page.locator(".item[role='button']").first.click()
            page.get_by_text("保存的规范化正文").wait_for()
            page.get_by_role("button",name="查看引文与审核").first.click()
            page.locator("mark").first.wait_for()
            assert page.locator("mark").first.inner_text()==QUOTE

            page.locator("#review-token").fill(TOKEN)
            page.locator('textarea[aria-label="审核原因"]').first.fill(
                "人工核对：引用确实唯一存在于当前保存的新闻中。"
            )
            page.get_by_role("button",name="提交审核记录").first.click()
            page.get_by_text("审核记录已保存",exact=False).wait_for()
            page.get_by_text("最近审核",exact=False).wait_for()
            assert page.evaluate("localStorage.length")==0

            page.locator('[data-view="events"]').click()
            page.get_by_text("相同长引用 · 保守分组").wait_for()
            page.locator(".item[role='button']").first.click()
            page.get_by_text("仅候选事件").wait_for()

            page.locator('[data-view="jobs"]').click()
            page.get_by_text("任务监控").wait_for()
            page.get_by_text("最近任务").wait_for()

            page.set_viewport_size({"width":390,"height":844})
            page.locator('[data-view="news"]').click()
            page.get_by_text("来源记录").wait_for()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
            assert errors == []
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
