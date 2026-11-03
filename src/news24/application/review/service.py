"""Optimistic, immutable reviewer decisions on exact source evidence and events.

A review means a human assessment of the *stored text*, not independent proof of
the underlying real-world event. Review decisions are never applied to edited
article revisions without a new review.
"""

from datetime import UTC, datetime
from typing import Any

from news24.infrastructure.sqlite.database import SQLiteNewsStore

CLAIM_DECISIONS = frozenset({
    "SUPPORTED_BY_TEXT", "NOT_SUPPORTED_BY_TEXT", "NEEDS_INVESTIGATION",
})
EVENT_DECISIONS = frozenset({"RELATED", "NOT_RELATED", "NEEDS_INVESTIGATION"})


def _validate(reason: str, reviewer: str, expected_version: int) -> None:
    if not 8 <= len(reason.strip()) <= 1000:
        raise ValueError("review reason must contain 8..1000 characters")
    if not 1 <= len(reviewer) <= 80:
        raise ValueError("reviewer identity is required")
    if expected_version < 0:
        raise ValueError("expected_version must be nonnegative")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _claim_row(store: SQLiteNewsStore, analysis_key: str, claim_index: int) -> Any:
    return store.conn.execute(
        """SELECT a.uid, a.revision_hash, n.revision_hash AS current_revision,
                  n.is_deleted, s.verdict AS match_verdict, s.statement, s.quote,
                  s.span_start, s.span_end
           FROM analysis_results a
           JOIN evidence_spans s ON s.analysis_key=a.analysis_key
           JOIN news n ON n.uid=a.uid
           WHERE a.analysis_key=? AND s.claim_index=?""",
        (analysis_key, claim_index),
    ).fetchone()


def claim_reviews(
    store: SQLiteNewsStore, analysis_key: str
) -> list[dict[str, Any]]:
    store.migrate()
    result = store.conn.execute(
        """SELECT r.id, r.claim_index, r.review_version, r.source_revision,
                  r.verdict, r.reviewer, r.reason, r.reviewed_at
           FROM claim_review_log r
           WHERE r.analysis_key=? AND r.review_version=(
             SELECT MAX(x.review_version) FROM claim_review_log x
             WHERE x.analysis_key=r.analysis_key AND x.claim_index=r.claim_index
           )
           ORDER BY r.claim_index""",
        (analysis_key,),
    ).fetchall()
    return [dict(row) for row in result]


def review_claim(
    store: SQLiteNewsStore,
    *,
    analysis_key: str,
    claim_index: int,
    expected_version: int,
    expected_source_revision: str,
    decision: str,
    reason: str,
    reviewer: str,
) -> dict[str, Any]:
    if decision not in CLAIM_DECISIONS:
        raise ValueError("unrecognized claim review decision")
    if claim_index < 0:
        raise ValueError("claim_index must be nonnegative")
    _validate(reason, reviewer, expected_version)
    store.migrate()
    try:
        store.conn.execute("BEGIN IMMEDIATE")
        claim = _claim_row(store, analysis_key, claim_index)
        if claim is None:
            raise ValueError("unknown analysis or claim index")
        if (
            claim["is_deleted"] or
            claim["current_revision"] != claim["revision_hash"] or
            claim["revision_hash"] != expected_source_revision
        ):
            raise ValueError("stale/deleted news revision; reload the current article")
        if decision == "SUPPORTED_BY_TEXT" and claim["match_verdict"] != "TEXT_MATCH_ONLY":
            raise ValueError("cannot approve a claim with missing or ambiguous quotation")
        current = int(store.conn.execute(
            """SELECT COALESCE(MAX(review_version),0) FROM claim_review_log
               WHERE analysis_key=? AND claim_index=?""",
            (analysis_key, claim_index),
        ).fetchone()[0])
        if current != expected_version:
            raise ValueError("review version conflict; reload latest review")
        new_version = current + 1
        timestamp = _now()
        cursor = store.conn.execute(
            """INSERT INTO claim_review_log
               (analysis_key, claim_index, review_version, source_revision,
                verdict, reviewer, reason, reviewed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                analysis_key, claim_index, new_version, expected_source_revision,
                decision, reviewer, reason.strip(), timestamp,
            ),
        )
        store.conn.execute("COMMIT")
        return {
            "id": cursor.lastrowid, "analysis_key": analysis_key,
            "claim_index": claim_index, "review_version": new_version,
            "verdict": decision, "reviewed_at": timestamp,
        }
    except Exception:
        if store.conn.in_transaction:
            store.conn.execute("ROLLBACK")
        raise


def event_reviews(store: SQLiteNewsStore, event_key: str) -> list[dict[str, Any]]:
    store.migrate()
    rows = store.conn.execute(
        """SELECT id, review_version, verdict, reviewer, reason, reviewed_at
           FROM event_review_log WHERE event_key=?
           ORDER BY review_version DESC""",
        (event_key,),
    ).fetchall()
    return [dict(row) for row in rows]


def review_event(
    store: SQLiteNewsStore,
    *,
    event_key: str,
    expected_version: int,
    decision: str,
    reason: str,
    reviewer: str,
) -> dict[str, Any]:
    if decision not in EVENT_DECISIONS:
        raise ValueError("unrecognized event review decision")
    _validate(reason, reviewer, expected_version)
    store.migrate()
    try:
        store.conn.execute("BEGIN IMMEDIATE")
        event = store.conn.execute(
            """SELECT e.event_key FROM event_clusters e
               JOIN event_members m ON m.event_key=e.event_key
               JOIN analysis_results a ON a.analysis_key=m.analysis_key
               JOIN news n ON n.uid=m.uid AND n.revision_hash=a.revision_hash
               WHERE e.event_key=? AND n.is_deleted=0 LIMIT 1""",
            (event_key,),
        ).fetchone()
        if event is None:
            raise ValueError("no active event members; reload the current candidates")
        version = int(store.conn.execute(
            "SELECT COALESCE(MAX(review_version),0) FROM event_review_log WHERE event_key=?",
            (event_key,),
        ).fetchone()[0])
        if version != expected_version:
            raise ValueError("event review version conflict; reload")
        timestamp = _now()
        cursor = store.conn.execute(
            """INSERT INTO event_review_log
               (event_key, review_version, verdict, reviewer, reason, reviewed_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event_key, version + 1, decision, reviewer, reason.strip(), timestamp),
        )
        store.conn.execute("COMMIT")
        return {
            "id": cursor.lastrowid, "event_key": event_key,
            "review_version": version + 1, "verdict": decision,
            "reviewed_at": timestamp,
        }
    except Exception:
        if store.conn.in_transaction:
            store.conn.execute("ROLLBACK")
        raise


def event_members(store: SQLiteNewsStore, event_key: str) -> list[dict[str, Any]]:
    store.migrate()
    rows = store.conn.execute(
        """SELECT m.uid, m.analysis_key, m.claim_index,
                  s.quote, s.statement, n.title, n.published_at,
                  n.source, a.revision_hash
           FROM event_members m
           JOIN analysis_results a ON a.analysis_key=m.analysis_key
           JOIN news n ON n.uid=m.uid AND n.revision_hash=a.revision_hash
           JOIN evidence_spans s ON s.analysis_key=m.analysis_key
             AND s.claim_index=m.claim_index
           WHERE m.event_key=? AND n.is_deleted=0
             AND s.verdict='TEXT_MATCH_ONLY'
           ORDER BY n.published_at DESC, m.uid""",
        (event_key,),
    ).fetchall()
    return [dict(row) for row in rows]
