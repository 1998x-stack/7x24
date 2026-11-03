"""Deterministic date-window reports over persisted news, without invented coverage."""

import hashlib
import html
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from news24.jobs.store import utc_time
from news24.storage.database import SQLiteNewsStore


def report_window(day: date, timezone: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone)
    start = datetime.combine(day, time.min, tzinfo=zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC)
    return start, end


def _safe_text(value: str, limit: int = 220) -> str:
    return html.escape(" ".join(value.split())[:limit], quote=True)


def generate_daily_report(
    store: SQLiteNewsStore,
    day: date,
    *,
    timezone: str = "Asia/Shanghai",
    sample_limit: int = 50,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Produce a reproducible report from *all* stored rows in a day window.

    Only the sample listing is capped. Totals are based on the entire DB result.
    Completeness is UNVERIFIED until externally checked source coverage exists.
    """
    if not 1 <= sample_limit <= 500:
        raise ValueError("sample_limit must be 1..500")
    store.migrate()
    start, end = report_window(day, timezone)
    since, until = utc_time(start), utc_time(end)
    clause = ("is_deleted=0 AND published_at IS NOT NULL "
              "AND julianday(published_at)>=julianday(?) "
              "AND julianday(published_at)<julianday(?)")
    params: tuple[str, str] = (since, until)
    conn = store.conn
    total = int(conn.execute(f"SELECT COUNT(*) FROM news WHERE {clause}", params).fetchone()[0])
    rows = conn.execute(
        f"""SELECT uid, source, title, content_text, published_at
            FROM news WHERE {clause}
            ORDER BY julianday(published_at) DESC, uid DESC LIMIT ?""",
        (*params, sample_limit),
    ).fetchall()
    categories = conn.execute(
        f"""SELECT c.category, COUNT(*) AS n
            FROM news_categories c JOIN news n ON n.uid=c.uid
            WHERE {clause.replace('is_deleted', 'n.is_deleted').replace('published_at', 'n.published_at')}
            GROUP BY c.category ORDER BY n DESC, c.category LIMIT 10""",
        params,
    ).fetchall()
    lines = [
        f"# 7x24 新闻数据库日报 — {day.isoformat()}",
        "",
        f"- 统计时区：{timezone}",
        f"- 窗口起点（UTC）：{since}",
        f"- 窗口终点（UTC，不包含）：{until}",
        f"- 本地数据库匹配新闻数：{total}",
        "- 来源覆盖完整性：未验证（不代表源站当日全部快讯）",
        "- 分析性质：确定性资料汇总，不构成投资判断",
        "",
        "## 分类计数（同一新闻可属于多个分类）",
    ]
    lines.extend(
        f"- {_safe_text(str(row['category']), 60)}：{row['n']}"
        for row in categories
    )
    if not categories:
        lines.append("- 无分类记录")
    lines.extend(["", f"## 最新样本（最多 {sample_limit} 条）"])
    for article in rows:
        label = _safe_text(str(article["title"] or article["uid"]), 100)
        body = _safe_text(str(article["content_text"]))
        lines.extend([
            "",
            f"### {label}",
            f"- 新闻 ID：{_safe_text(str(article['uid']), 100)}",
            f"- 来源：{_safe_text(str(article['source']), 50)}",
            f"- 发布时间：{_safe_text(str(article['published_at']), 40)}",
            "",
            body,
        ])
    if total > len(rows):
        lines.extend(["", f"注意：正文仅展示 {len(rows)} 条样本，其余 {total-len(rows)} 条已计入统计。"])
    markdown = "\n".join(lines) + "\n"
    digest = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    key = f"daily:{timezone}:{day.isoformat()}"
    timestamp = utc_time(now or datetime.now(UTC))
    try:
        conn.execute("BEGIN IMMEDIATE")
        previous = conn.execute(
            "SELECT content_sha256, revision FROM report_runs WHERE report_key=?", (key,)
        ).fetchone()
        if previous is not None and previous["content_sha256"] == digest:
            conn.execute("COMMIT")
            return {"report_key": key, "state": "NO_CHANGES", "news_count": total,
                    "revision": int(previous["revision"]), "completeness": "UNVERIFIED"}
        revision = int(previous["revision"]) + 1 if previous else 1
        conn.execute(
            """INSERT INTO report_runs (
                 report_key, report_date, timezone, period_start, period_end,
                 news_count, completeness, markdown, content_sha256, revision, generated_at
               ) VALUES (?, ?, ?, ?, ?, ?, 'UNVERIFIED', ?, ?, ?, ?)
               ON CONFLICT(report_key) DO UPDATE SET
                 news_count=excluded.news_count, markdown=excluded.markdown,
                 content_sha256=excluded.content_sha256, revision=excluded.revision,
                 generated_at=excluded.generated_at""",
            (key, day.isoformat(), timezone, since, until, total,
             markdown, digest, revision, timestamp),
        )
        conn.execute(
            """INSERT INTO report_revisions
               (report_key, revision, markdown, content_sha256, generated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (key, revision, markdown, digest, timestamp),
        )
        conn.execute("COMMIT")
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    return {"report_key": key, "state": "SUCCEEDED", "news_count": total,
            "revision": revision, "completeness": "UNVERIFIED"}


def get_report(
    store: SQLiteNewsStore, day: date, *, timezone: str = "Asia/Shanghai"
) -> str | None:
    store.migrate()
    key = f"daily:{timezone}:{day.isoformat()}"
    row = store.conn.execute(
        "SELECT markdown FROM report_runs WHERE report_key=?", (key,)
    ).fetchone()
    return str(row["markdown"]) if row else None
