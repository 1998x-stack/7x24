"""Loopback-only, no-dependency research API and provenance workbench.

Read endpoints are scoped to the local machine. Write endpoints additionally
require a constant-time checked, operator-provided bearer token and same-origin
request. News/LLM text is returned as data and never inserted as HTML.
"""

import hmac
import json
import os
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from news24.application.intelligence.service import (
    analysis_history,
    event_candidates,
    evidence_for,
)
from news24.application.observability.health import runtime_health
from news24.application.review.service import (
    claim_reviews,
    event_members,
    event_reviews,
    review_claim,
    review_event,
)
from news24.infrastructure.sqlite.database import SQLiteNewsStore
from news24.infrastructure.sqlite.job_store import JobStore

MAX_REQUEST_BODY = 16384
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


def _positive_number(value: str, *, maximum: int, minimum: int = 0) -> int:
    number = int(value)
    if not minimum <= number <= maximum:
        raise ValueError(f"number must be between {minimum} and {maximum}")
    return number


def _query_one(query: dict[str, list[str]], name: str, default: str = "") -> str:
    values = query.get(name, [default])
    if len(values) != 1:
        raise ValueError(f"only one {name} is allowed")
    return values[0]


def read_news(
    store: SQLiteNewsStore,
    *,
    search: str = "",
    limit: int = 30,
    offset: int = 0,
) -> dict[str, Any]:
    """Bounded list with count independent of displayed news page."""
    if not 1 <= limit <= 100 or not 0 <= offset <= 100000:
        raise ValueError("invalid pagination limits")
    if len(search) > 120:
        raise ValueError("query too long")
    where = "WHERE is_deleted=0"
    params: list[Any] = []
    if search:
        where += " AND (title LIKE ? ESCAPE '\\' OR content_text LIKE ? ESCAPE '\\')"
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params += [f"%{escaped}%", f"%{escaped}%"]
    total = int(store.conn.execute(
        f"SELECT COUNT(*) FROM news {where}", params
    ).fetchone()[0])
    rows = store.conn.execute(
        f"""SELECT uid, source, title, published_at, last_fetched_at,
                   substr(content_text, 1, 240) AS excerpt, revision_hash
            FROM news {where}
            ORDER BY julianday(published_at) DESC, uid DESC LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    ).fetchall()
    return {
        "total": total, "items": [dict(row) for row in rows],
        "next_offset": offset + len(rows) if offset + len(rows) < total else None,
    }


def article_detail(store: SQLiteNewsStore, uid: str) -> dict[str, Any]:
    row = store.conn.execute(
        "SELECT article_json, revision_hash, is_deleted FROM news WHERE uid=?",
        (uid,),
    ).fetchone()
    if row is None:
        raise LookupError("article not found")
    result: dict[str, Any] = json.loads(row["article_json"])
    result["revision_hash"] = row["revision_hash"]
    result["is_deleted"] = bool(row["is_deleted"])
    # Source payload remains raw JSON for inspection. It is never rendered as markup.
    return result


def _event_detail(store: SQLiteNewsStore, key: str) -> dict[str, Any]:
    row = store.conn.execute(
        "SELECT event_key, local_day, normalized_quote, status FROM event_clusters "
        "WHERE event_key=?", (key,),
    ).fetchone()
    if row is None:
        raise LookupError("event candidate not found")
    return {
        **dict(row), "members": event_members(store, key),
        "reviews": event_reviews(store, key),
    }


def make_handler(
    db_path: str | Path,
    *,
    review_token: str | None = None,
    reviewer: str = "local-operator",
) -> type[BaseHTTPRequestHandler]:
    """Build isolated handler class; token is never returned to the browser."""
    path = str(db_path)
    secret = review_token or ""
    if secret and len(secret) < 16:
        raise ValueError("NEWS24_REVIEW_TOKEN must contain at least 16 characters")
    if not 1 <= len(reviewer) <= 80:
        raise ValueError("invalid reviewer label")

    class WorkbenchHandler(BaseHTTPRequestHandler):
        server_version = "News24Workbench/1.0"

        def log_message(self, format: str, *args: object) -> None:
            # Avoid logging sensitive URLs, claims, tokens and submitted reason text.
            return

        def _header(self, name: str, value: str) -> None:
            self.send_header(name, value)

        def _start(self, status: int, kind: str, length: int) -> None:
            self.send_response(status)
            self._header("Content-Type", kind)
            self._header("Content-Length", str(length))
            self._header("X-Content-Type-Options", "nosniff")
            self._header("X-Frame-Options", "DENY")
            self._header("Referrer-Policy", "no-referrer")
            self._header("Cache-Control", "no-store")
            self._header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; img-src 'self'; base-uri 'none'; "
                "form-action 'self'; frame-ancestors 'none'",
            )
            self.end_headers()

        def _response(
            self, data: object, status: int = HTTPStatus.OK
        ) -> None:
            raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
            self._start(status, "application/json; charset=utf-8", len(raw))
            self.wfile.write(raw)

        def _error(self, code: int, message: str) -> None:
            self._response({"error": message, "ok": False}, code)

        def _local_host(self) -> bool:
            host = (self.headers.get("Host") or "").lower().split(":")[0]
            return host in ("localhost", "127.0.0.1", "[::1]")

        def _same_origin(self) -> bool:
            origin = self.headers.get("Origin")
            if not origin:
                return False
            parts = urlsplit(origin)
            host = self.headers.get("Host") or ""
            return (
                parts.scheme == "http" and parts.netloc.lower() == host.lower()
                and parts.path == "" and parts.query == ""
            )

        def do_GET(self) -> None:
            if not self._local_host():
                self._error(HTTPStatus.FORBIDDEN, "invalid host")
                return
            url = urlsplit(self.path)
            if url.path in ASSETS:
                name, mime = ASSETS[url.path]
                resource = resources.files("news24.interfaces.web").joinpath(name)
                data = resource.read_bytes()
                self._start(HTTPStatus.OK, mime, len(data))
                self.wfile.write(data)
                return
            if not url.path.startswith("/api/"):
                self._error(HTTPStatus.NOT_FOUND, "unknown route")
                return
            try:
                q = parse_qs(url.query, keep_blank_values=True)
                with SQLiteNewsStore(path) as store:
                    store.migrate()
                    route = url.path
                    if route == "/api/health":
                        answer: object = runtime_health(store)
                    elif route == "/api/news":
                        answer = read_news(
                            store, search=_query_one(q, "q"),
                            limit=_positive_number(
                                _query_one(q, "limit", "30"), minimum=1, maximum=100
                            ),
                            offset=_positive_number(
                                _query_one(q, "offset", "0"), maximum=100000
                            ),
                        )
                    elif route == "/api/article":
                        answer = article_detail(store, _query_one(q, "uid"))
                    elif route == "/api/analyses":
                        answer = {"items": analysis_history(store, _query_one(q, "uid"))}
                    elif route == "/api/evidence":
                        key = _query_one(q, "key")
                        answer = {
                            "items": evidence_for(store, key),
                            "reviews": claim_reviews(store, key),
                        }
                    elif route == "/api/events":
                        answer = {"items": event_candidates(
                            store, day=_query_one(q, "day") or None,
                            limit=_positive_number(
                                _query_one(q, "limit", "50"), minimum=1, maximum=200
                            ),
                        )}
                    elif route == "/api/event":
                        answer = _event_detail(store, _query_one(q, "key"))
                    elif route == "/api/jobs":
                        answer = {"items": [
                            {
                                "job_key": row["job_key"], "kind": row["kind"],
                                "state": row["state"], "attempts": row["attempts"],
                                "max_attempts": row["max_attempts"],
                                "updated_at": row["updated_at"],
                            } for row in JobStore(store).latest(
                                _positive_number(
                                    _query_one(q, "limit", "30"),
                                    minimum=1, maximum=100,
                                )
                            )
                        ]}
                    elif route == "/api/evaluations":
                        rows = store.conn.execute(
                            "SELECT run_id, dataset_sha256, algorithm, total_cases, "
                            "passed_cases, metrics_json, evaluated_at "
                            "FROM evaluation_runs ORDER BY evaluated_at DESC LIMIT 20"
                        ).fetchall()
                        answer = {"items": [dict(row) for row in rows]}
                    else:
                        raise LookupError("unknown endpoint")
                self._response(answer)
            except (ValueError, TypeError) as exc:
                self._error(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))
            except LookupError as exc:
                self._error(HTTPStatus.NOT_FOUND, str(exc))
            except (sqlite3.Error, OSError):
                self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "database error")

        def do_POST(self) -> None:
            if not self._local_host() or not self._same_origin():
                self._error(HTTPStatus.FORBIDDEN, "same-origin localhost requests only")
                return
            if not secret:
                self._error(HTTPStatus.FORBIDDEN, "reviews disabled")
                return
            token = self.headers.get("Authorization", "")
            expected = "Bearer " + secret
            if not hmac.compare_digest(token, expected):
                self._error(HTTPStatus.UNAUTHORIZED, "invalid review credentials")
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self._error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "JSON content required")
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_REQUEST_BODY:
                    raise ValueError("request too large or empty")
                data = json.loads(self.rfile.read(size).decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("JSON object expected")
                with SQLiteNewsStore(path) as store:
                    if self.path == "/api/reviews/claim":
                        result = review_claim(
                            store,
                            analysis_key=str(data["analysis_key"]),
                            claim_index=int(data["claim_index"]),
                            expected_version=int(data["expected_version"]),
                            expected_source_revision=str(data["expected_source_revision"]),
                            decision=str(data["decision"]),
                            reason=str(data["reason"]),
                            reviewer=reviewer,
                        )
                    elif self.path == "/api/reviews/event":
                        result = review_event(
                            store,
                            event_key=str(data["event_key"]),
                            expected_version=int(data["expected_version"]),
                            decision=str(data["decision"]),
                            reason=str(data["reason"]),
                            reviewer=reviewer,
                        )
                    else:
                        raise LookupError("unknown review endpoint")
                self._response({"ok": True, **result}, HTTPStatus.CREATED)
            except (ValueError, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
                msg = str(exc)
                if "conflict" in msg or "stale" in msg:
                    self._error(HTTPStatus.CONFLICT, msg)
                else:
                    self._error(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid review: " + msg[:120])
            except LookupError:
                self._error(HTTPStatus.NOT_FOUND, "unknown endpoint")
            except (sqlite3.Error, OSError):
                self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "review storage error")

    return WorkbenchHandler


def serve(
    db_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    review_token: str | None = None,
    reviewer: str = "local-operator",
) -> None:
    if host != "127.0.0.1":
        raise ValueError("workbench deliberately binds 127.0.0.1 only")
    if not 1 <= port <= 65535:
        raise ValueError("invalid port")
    with SQLiteNewsStore(db_path) as store:
        store.migrate()
    handler = make_handler(db_path, review_token=review_token, reviewer=reviewer)
    with ThreadingHTTPServer((host, port), handler) as server:
        print(f"News24 local workbench: http://127.0.0.1:{port}/")
        server.serve_forever(poll_interval=0.25)


def serve_from_env(db_path: str | Path, port: int) -> None:
    serve(
        db_path, port=port,
        review_token=os.getenv("NEWS24_REVIEW_TOKEN"),
        reviewer=os.getenv("NEWS24_REVIEWER", "local-operator"),
    )
