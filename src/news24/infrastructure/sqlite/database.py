"""Transactional SQLite/WAL repository for feed articles and checkpoints.

A fetched batch is committed as ONE transaction: raw snapshots, deduplicated
articles, revisions, categories, and (only on complete coverage) the watermark.
"""

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

from news24.domain.news import NewsArticle
from news24.domain.ingestion import FetchBatch

SCHEMA_VERSION = 4


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _as_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _revision_hash(article: NewsArticle) -> str:
    # Receipt timestamps are deliberately excluded: repeated polls are idempotent.
    data = article.model_dump(mode="json", exclude={"fetched_at"})
    return hashlib.sha256(_json(data).encode("utf-8")).hexdigest()


class SQLiteNewsStore:
    """Single-process SQLite connection. Close explicitly or use as context manager."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=10000")
        if str(path) != ":memory:":
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")

    def __enter__(self) -> "SQLiteNewsStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    def migrate(self) -> int:
        """Upgrade old v1 databases incrementally and atomically."""
        version = int(self.conn.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            raise RuntimeError(
                f"database version {version} newer than code {SCHEMA_VERSION}"
            )
        names = {1: "0001_initial.sql", 2: "0002_jobs.sql", 3: "0003_intelligence.sql", 4: "0004_review.sql"}
        for next_version in range(version + 1, SCHEMA_VERSION + 1):
            script = (
                resources.files("news24.infrastructure.sqlite.migrations")
                .joinpath(names[next_version])
                .read_text(encoding="utf-8")
            )
            try:
                self.conn.executescript(
                    "BEGIN IMMEDIATE;\n"
                    + script
                    + f"\nPRAGMA user_version={next_version};\nCOMMIT;"
                )
            except sqlite3.Error:
                if self.conn.in_transaction:
                    self.conn.execute("ROLLBACK")
                raise
        return SCHEMA_VERSION

    def _require_schema(self) -> None:
        if int(self.conn.execute("PRAGMA user_version").fetchone()[0]) != SCHEMA_VERSION:
            raise RuntimeError("database not migrated: run 'news24 db migrate'")

    def checkpoint(self, source: str, category: str) -> int | None:
        self._require_schema()
        row = self.conn.execute(
            "SELECT last_seen_id FROM source_checkpoints WHERE source=? AND category=?",
            (source, category),
        ).fetchone()
        return int(row["last_seen_id"]) if row else None

    def begin_run(self, run_id: str, source: str, category: str) -> int | None:
        self._require_schema()
        before = self.checkpoint(source, category)
        self.conn.execute(
            """
            INSERT INTO ingestion_runs
              (run_id, source, category, started_at, status, checkpoint_before)
            VALUES (?, ?, ?, ?, 'RUNNING', ?)
            """,
            (run_id, source, category, _utc_now(), str(before) if before is not None else None),
        )
        return before

    def finish_failed(self, run_id: str, error: Exception) -> None:
        # A failure NEVER advances the checkpoint.
        self.conn.execute(
            """
            UPDATE ingestion_runs
            SET status='FAILED', finished_at=?, error_message=?
            WHERE run_id=? AND status='RUNNING'
            """,
            (_utc_now(), f"{type(error).__name__}: {error}"[:1024], run_id),
        )

    def recover_interrupted(self) -> int:
        """Mark left-behind RUNNING attempts failed; safe for a single writer only."""
        self._require_schema()
        cursor = self.conn.execute(
            """
            UPDATE ingestion_runs
            SET status='FAILED', finished_at=?, error_message='interrupted before commit'
            WHERE status='RUNNING'
            """,
            (_utc_now(),),
        )
        return cursor.rowcount

    def _upsert_article(self, article: NewsArticle, category: str, recorded_at: str) -> str:
        revision_hash = _revision_hash(article)
        prior = self.conn.execute(
            "SELECT revision_hash FROM news WHERE uid=?", (article.uid,)
        ).fetchone()
        data = (
            article.source,
            article.source_id,
            article.title,
            article.content_raw,
            article.content_text,
            _as_iso(article.published_at),
            _as_iso(article.updated_at),
            _as_iso(article.fetched_at),
            article.source_url,
            article.content_hash,
            revision_hash,
            int(article.is_deleted),
            int(article.is_repeated),
            _json(article.raw),
            article.model_dump_json(),
        )
        if prior is None:
            self.conn.execute(
                """
                INSERT INTO news (
                    uid, source, source_id, title, content_raw, content_text,
                    published_at, updated_at, first_fetched_at, last_fetched_at,
                    source_url, content_hash, revision_hash, is_deleted, is_repeated, raw_json, article_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (article.uid, *data[:7], data[7], *data[7:]),
            )
            result = "inserted"
        elif prior["revision_hash"] != revision_hash:
            self.conn.execute(
                """
                UPDATE news SET title=?, content_raw=?, content_text=?, published_at=?,
                    updated_at=?, last_fetched_at=?, source_url=?, content_hash=?,
                    revision_hash=?, is_deleted=?, is_repeated=?, raw_json=?, article_json=?
                WHERE uid=?
                """,
                (
                    article.title, article.content_raw, article.content_text,
                    _as_iso(article.published_at), _as_iso(article.updated_at),
                    _as_iso(article.fetched_at), article.source_url, article.content_hash,
                    revision_hash, int(article.is_deleted), int(article.is_repeated),
                    _json(article.raw), article.model_dump_json(), article.uid,
                ),
            )
            result = "revised"
        else:
            self.conn.execute(
                "UPDATE news SET last_fetched_at=?, article_json=? WHERE uid=?",
                (_as_iso(article.fetched_at), article.model_dump_json(), article.uid),
            )
            result = "unchanged"

        if result in ("inserted", "revised"):
            version = int(
                self.conn.execute(
                    "SELECT COUNT(*) FROM news_revisions WHERE uid=?", (article.uid,)
                ).fetchone()[0]
            ) + 1
            self.conn.execute(
                """
                INSERT INTO news_revisions
                    (uid, version, revision_hash, content_hash, snapshot_json, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    article.uid, version, revision_hash, article.content_hash,
                    article.model_dump_json(), recorded_at,
                ),
            )

        for tag in set(article.categories + article.tags + ([category] if category != "all" else [])):
            if tag:
                self.conn.execute(
                    "INSERT OR IGNORE INTO news_categories (uid, category) VALUES (?, ?)",
                    (article.uid, tag),
                )
        return result

    def apply_batch(
        self,
        run_id: str,
        source: str,
        category: str,
        batch: FetchBatch,
    ) -> dict[str, Any]:
        """Atomically ingest a fetched batch and conditionally advance its checkpoint."""
        self._require_schema()
        inserted = 0
        revised = 0
        now = _utc_now()
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            run = self.conn.execute(
                "SELECT status FROM ingestion_runs WHERE run_id=? AND source=? AND category=?",
                (run_id, source, category),
            ).fetchone()
            if run is None or run["status"] != "RUNNING":
                raise ValueError("run not found or not RUNNING")
            for page in batch.pages:
                raw = _json(page.raw)
                digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                self.conn.execute(
                    """
                    INSERT INTO source_snapshots
                        (run_id, source, category, page, fetched_at,
                         payload_sha256, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id, source, category, page.number,
                        page.fetched_at.isoformat(), digest, raw,
                    ),
                )
            # One source ID may appear in multiple requested classifications.
            for article in batch.articles:
                outcome = self._upsert_article(article, category, now)
                inserted += outcome == "inserted"
                revised += outcome == "revised"

            after = self.checkpoint(source, category)
            if batch.complete and batch.checkpoint_after is not None:
                new_id = max(batch.checkpoint_after, after or 0)
                if after is None or new_id > after:
                    self.conn.execute(
                        """
                        INSERT INTO source_checkpoints
                            (source, category, last_seen_id, updated_at, run_id)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(source, category) DO UPDATE SET
                            last_seen_id=excluded.last_seen_id,
                            updated_at=excluded.updated_at,
                            run_id=excluded.run_id
                        """,
                        (source, category, str(new_id), now, run_id),
                    )
                    after = new_id

            status = "INCOMPLETE" if not batch.complete else (
                "NO_CHANGES" if inserted == 0 and revised == 0 else "SUCCEEDED"
            )
            self.conn.execute(
                """
                UPDATE ingestion_runs SET status=?, finished_at=?,
                    pages_fetched=?, articles_seen=?, articles_inserted=?,
                    articles_revised=?, checkpoint_after=?
                WHERE run_id=?
                """,
                (
                    status, now, batch.pages_fetched, len(batch.articles),
                    inserted, revised, str(after) if after is not None else None, run_id,
                ),
            )
            self.conn.execute("COMMIT")
        except Exception:
            if self.conn.in_transaction:
                self.conn.execute("ROLLBACK")
            raise
        return {
            "run_id": run_id, "status": status, "pages": batch.pages_fetched,
            "seen": len(batch.articles), "inserted": inserted, "revised": revised,
            "checkpoint": after, "reason": batch.reason,
        }

    def statistics(self) -> dict[str, int]:
        self._require_schema()
        result: dict[str, int] = {}
        for table in (
            "news", "news_revisions", "source_snapshots",
            "source_checkpoints", "ingestion_runs",
        ):
            result[table] = int(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return result

    def revisions(self, uid: str) -> list[dict[str, Any]]:
        self._require_schema()
        rows = self.conn.execute(
            "SELECT version, revision_hash, snapshot_json FROM news_revisions "
            "WHERE uid=? ORDER BY version", (uid,)
        ).fetchall()
        return [dict(row) for row in rows]

    def recent(self, count: int = 20) -> list[NewsArticle]:
        self._require_schema()
        if count < 1:
            raise ValueError("count must be positive")
        rows = self.conn.execute(
            "SELECT * FROM news ORDER BY published_at DESC, uid DESC LIMIT ?", (count,)
        ).fetchall()
        return [self._row_article(row) for row in rows]

    @staticmethod
    def _row_article(row: sqlite3.Row) -> NewsArticle:
        return NewsArticle.model_validate_json(row["article_json"])

    def search(self, query: str, count: int = 20) -> list[NewsArticle]:
        self._require_schema()
        if not query.strip() or not 1 <= count <= 200:
            raise ValueError("query must not be empty and count must be 1..200")
        # Trigram only indexes tokens of >=3 unicode characters.
        if len(query) < 3:
            rows = self.conn.execute(
                "SELECT * FROM news WHERE title LIKE ? OR content_text LIKE ? "
                "ORDER BY published_at DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", count),
            ).fetchall()
        else:
            phrase = '"' + query.replace('"', '""') + '"'
            rows = self.conn.execute(
                "SELECT news.* FROM news_fts JOIN news ON news_fts.rowid=news.rowid "
                "WHERE news_fts MATCH ? ORDER BY news.published_at DESC LIMIT ?",
                (phrase, count),
            ).fetchall()
        return [self._row_article(row) for row in rows]
