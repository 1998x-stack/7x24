"""Evidence spans are verified against stored text; semantics remain unverified."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from news24.application.intelligence.ports import AnalysisProvider
from news24.application.intelligence.prompt import SYSTEM_PROMPT
from news24.domain.analysis import AnalysisSpec
from news24.domain.news import NewsArticle
from news24.infrastructure.sqlite.database import SQLiteNewsStore

_PROMPT_SHA = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()
_SHANGHAI = ZoneInfo("Asia/Shanghai")


def _fingerprint(parts: list[str]) -> str:
    return hashlib.sha256(
        json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _evidence_status(text: str, quote: str) -> tuple[str, int | None, int | None]:
    first = text.find(quote)
    if first < 0:
        return "NOT_FOUND", None, None
    if text.find(quote, first + 1) != -1:
        return "AMBIGUOUS", None, None
    return "TEXT_MATCH_ONLY", first, first + len(quote)


async def analyze_article(
    store: SQLiteNewsStore,
    uid: str,
    spec: AnalysisSpec,
    provider: AnalysisProvider,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Idempotently analyze a particular article revision with a strict source gate."""
    store.migrate()
    source = store.conn.execute(
        "SELECT revision_hash, article_json FROM news WHERE uid=?", (uid,)
    ).fetchone()
    if source is None:
        raise ValueError(f"unknown article uid: {uid}")
    article = NewsArticle.model_validate_json(source["article_json"])
    revision = str(source["revision_hash"])
    input_hash = _fingerprint([article.title or "", article.content_text])
    key = _fingerprint([
        uid, revision, input_hash, spec.provider, spec.model,
        spec.prompt_version, _PROMPT_SHA, spec.schema_version,
    ])
    cached = store.conn.execute(
        "SELECT status FROM analysis_results WHERE analysis_key=?", (key,)
    ).fetchone()
    if cached is not None:
        return {"analysis_key": key, "status": str(cached["status"]), "cached": True}

    reply = await provider.analyze(article.title, article.content_text, spec)
    evidence: list[tuple[int, str, str, str, int | None, int | None]] = []
    for index, claim in enumerate(reply.data.claims):
        verdict, begin, end = _evidence_status(article.content_text, claim.quote)
        evidence.append((index, claim.statement, claim.quote, verdict, begin, end))
    supported = sum(verdict == "TEXT_MATCH_ONLY" for _, _, _, verdict, _, _ in evidence)
    if not evidence or supported == len(evidence):
        state = "ACCEPTED"
    elif supported:
        state = "PARTIAL"
    else:
        state = "REJECTED"
    sentiment = reply.data.sentiment if state != "REJECTED" else None
    timestamp = (now or datetime.now(UTC)).astimezone(UTC).isoformat()
    data_json = reply.data.model_dump_json()

    try:
        store.conn.execute("BEGIN IMMEDIATE")
        current = store.conn.execute(
            "SELECT revision_hash FROM news WHERE uid=?", (uid,)
        ).fetchone()
        if current is None or current["revision_hash"] != revision:
            raise RuntimeError("article changed during model inference; retry latest revision")
        existing = store.conn.execute(
            "SELECT status FROM analysis_results WHERE analysis_key=?", (key,)
        ).fetchone()
        if existing is not None:
            store.conn.execute("COMMIT")
            return {"analysis_key": key, "status": str(existing["status"]), "cached": True}

        store.conn.execute(
            """INSERT INTO analysis_results (
                analysis_key, uid, revision_hash, input_hash,
                provider, model, prompt_version, prompt_sha256, schema_version,
                status, sentiment, output_json, response_id,
                input_tokens, output_tokens, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                key, uid, revision, input_hash, spec.provider, spec.model,
                spec.prompt_version, _PROMPT_SHA, spec.schema_version, state,
                sentiment, data_json, reply.response_id, reply.input_tokens,
                reply.output_tokens, timestamp,
            ),
        )
        for index, statement, quote, verdict, begin, end in evidence:
            store.conn.execute(
                """INSERT INTO evidence_spans
                   (analysis_key, claim_index, statement, quote,
                    span_start, span_end, verdict)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (key, index, statement, quote, begin, end, verdict),
            )
            if verdict != "TEXT_MATCH_ONLY" or len(" ".join(quote.split())) < 12:
                continue
            # Identical, sufficiently specific quotes, same local calendar day.
            # This is a candidate grouping, not fact checking or cross-source proof.
            if article.published_at is None:
                continue
            day = article.published_at.astimezone(_SHANGHAI).date().isoformat()
            signature = " ".join(quote.split())
            cluster = _fingerprint([day, signature])
            store.conn.execute(
                """INSERT OR IGNORE INTO event_clusters
                   (event_key, local_day, normalized_quote, created_at)
                   VALUES (?, ?, ?, ?)""",
                (cluster, day, signature, timestamp),
            )
            store.conn.execute(
                """INSERT OR IGNORE INTO event_members
                   (event_key, analysis_key, claim_index, uid)
                   VALUES (?, ?, ?, ?)""",
                (cluster, key, index, uid),
            )
        store.conn.execute("COMMIT")
    except Exception:
        if store.conn.in_transaction:
            store.conn.execute("ROLLBACK")
        raise

    return {
        "analysis_key": key, "uid": uid, "status": state, "cached": False,
        "sentiment": sentiment, "claims": len(evidence), "text_matched": supported,
        "model": spec.model, "prompt_version": spec.prompt_version,
        "source_revision": revision,
    }


def analysis_history(store: SQLiteNewsStore, uid: str) -> list[dict[str, Any]]:
    store.migrate()
    rows = store.conn.execute(
        """SELECT analysis_key, revision_hash, input_hash,
                  provider, model, prompt_version, prompt_sha256, schema_version,
                  status, sentiment, created_at, input_tokens, output_tokens
           FROM analysis_results WHERE uid=?
           ORDER BY created_at DESC, analysis_key DESC""",
        (uid,),
    ).fetchall()
    return [dict(row) for row in rows]


def evidence_for(store: SQLiteNewsStore, analysis_key: str) -> list[dict[str, Any]]:
    store.migrate()
    rows = store.conn.execute(
        """SELECT claim_index, statement, quote, span_start, span_end, verdict
           FROM evidence_spans WHERE analysis_key=? ORDER BY claim_index""",
        (analysis_key,),
    ).fetchall()
    return [dict(row) for row in rows]


def event_candidates(
    store: SQLiteNewsStore, *, day: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    """Only count evidence on currently active source revisions."""
    store.migrate()
    if not 1 <= limit <= 200:
        raise ValueError("limit must be 1..200")
    params: list[str | int] = []
    where = ""
    if day is not None:
        where = "AND e.local_day=?"
        params.append(day)
    params.append(limit)
    rows = store.conn.execute(
        f"""SELECT e.event_key, e.local_day, e.normalized_quote, e.status,
                   COUNT(DISTINCT m.uid) AS distinct_articles
            FROM event_clusters e
            JOIN event_members m ON m.event_key=e.event_key
            JOIN analysis_results a ON a.analysis_key=m.analysis_key
            JOIN news n ON n.uid=m.uid AND n.revision_hash=a.revision_hash
            JOIN evidence_spans s
              ON s.analysis_key=m.analysis_key AND s.claim_index=m.claim_index
            WHERE n.is_deleted=0 AND s.verdict='TEXT_MATCH_ONLY' {where}
            GROUP BY e.event_key
            ORDER BY distinct_articles DESC, e.local_day DESC, e.event_key
            LIMIT ?""",
        params,
    ).fetchall()
    return [dict(row) for row in rows]
