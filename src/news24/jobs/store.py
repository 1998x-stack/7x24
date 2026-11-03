"""SQLite-backed at-least-once queue with atomic claim and bounded retries.

The worker is designed for one active runner. Cross-process claims use BEGIN IMMEDIATE
and leases so even accidental overlapping runners do not claim the same job.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from news24.storage.database import SQLiteNewsStore

KINDS = frozenset({"collect", "report", "probe", "analyze"})


def utc_time(value: datetime) -> str:
    if value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat(timespec="microseconds")


class JobStore:
    def __init__(self, database: SQLiteNewsStore) -> None:
        self.database = database
        self.conn = database.conn

    def enqueue(
        self,
        key: str,
        kind: str,
        payload: dict[str, Any],
        *,
        now: datetime,
        max_attempts: int = 3,
    ) -> bool:
        if kind not in KINDS:
            raise ValueError(f"unsupported kind: {kind}")
        if not key or not 1 <= max_attempts <= 10:
            raise ValueError("job key must be set and max_attempts must be 1..10")
        timestamp = utc_time(now)
        cursor = self.conn.execute(
            """INSERT OR IGNORE INTO job_queue (
                  job_key, kind, payload_json, state, max_attempts,
                  available_at, created_at, updated_at
               ) VALUES (?, ?, ?, 'QUEUED', ?, ?, ?, ?)""",
            (key, kind, json.dumps(payload, sort_keys=True), max_attempts,
             timestamp, timestamp, timestamp),
        )
        return cursor.rowcount == 1

    def claim(
        self, owner: str, *, now: datetime, lease_seconds: int = 180
    ) -> dict[str, Any] | None:
        if not owner or lease_seconds < 10:
            raise ValueError("owner required; lease_seconds must be >=10")
        timestamp = utc_time(now)
        lease_until = utc_time(now + timedelta(seconds=lease_seconds))
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            row = self.conn.execute(
                """SELECT * FROM job_queue
                   WHERE state IN ('QUEUED','RETRY_WAIT') AND available_at<=?
                   ORDER BY available_at, created_at, job_key LIMIT 1""",
                (timestamp,),
            ).fetchone()
            if row is None:
                self.conn.execute("COMMIT")
                return None
            attempt = int(row["attempts"]) + 1
            self.conn.execute(
                """UPDATE job_queue SET state='RUNNING', attempts=?,
                   owner_id=?, lease_until=?, updated_at=?, last_error=NULL
                   WHERE job_key=?""",
                (attempt, owner, lease_until, timestamp, row["job_key"]),
            )
            self.conn.execute(
                """INSERT INTO job_attempts (job_key, attempt, started_at)
                   VALUES (?, ?, ?)""",
                (row["job_key"], attempt, timestamp),
            )
            self.conn.execute("COMMIT")
            return {
                "key": row["job_key"], "kind": row["kind"],
                "payload": json.loads(row["payload_json"]), "attempt": attempt,
                "owner": owner, "max_attempts": int(row["max_attempts"]),
                "lease_until": lease_until,
            }
        except Exception:
            if self.conn.in_transaction:
                self.conn.execute("ROLLBACK")
            raise

    def _settle(
        self, job: dict[str, Any], *, now: datetime,
        result: dict[str, Any] | None = None, error: str | None = None,
    ) -> str:
        timestamp = utc_time(now)
        key = str(job["key"])
        owner = str(job["owner"])
        attempts = int(job["attempt"])
        max_attempts = int(job["max_attempts"])
        state = ("SUCCEEDED" if error is None else
                 "FAILED" if attempts >= max_attempts else "RETRY_WAIT")
        available_at = timestamp
        if state == "RETRY_WAIT":
            delay = min(5 * (2 ** (attempts - 1)), 300)
            available_at = utc_time(now + timedelta(seconds=delay))
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            current = self.conn.execute(
                "SELECT state, owner_id, attempts FROM job_queue WHERE job_key=?",
                (key,),
            ).fetchone()
            if (current is None or current["state"] != "RUNNING"
                    or current["owner_id"] != owner or current["attempts"] != attempts):
                raise ValueError("stale job completion; owner or attempt mismatch")
            self.conn.execute(
                """UPDATE job_queue SET state=?, available_at=?,
                   lease_until=NULL, owner_id=NULL, updated_at=?, finished_at=?,
                   last_error=?, result_json=?
                   WHERE job_key=?""",
                (state, available_at, timestamp,
                 timestamp if state != "RETRY_WAIT" else None,
                 error[:1024] if error else None,
                 json.dumps(result, sort_keys=True) if result is not None else None,
                 key),
            )
            self.conn.execute(
                """UPDATE job_attempts SET ended_at=?, outcome=?, error_message=?
                   WHERE job_key=? AND attempt=?""",
                (timestamp, state, error[:1024] if error else None, key, attempts),
            )
            self.conn.execute("COMMIT")
            return state
        except Exception:
            if self.conn.in_transaction:
                self.conn.execute("ROLLBACK")
            raise

    def succeed(
        self, job: dict[str, Any], result: dict[str, Any], *, now: datetime
    ) -> str:
        return self._settle(job, now=now, result=result)

    def fail(self, job: dict[str, Any], error: Exception, *, now: datetime) -> str:
        return self._settle(job, now=now, error=f"{type(error).__name__}: {error}")

    def recover_expired(self, *, now: datetime) -> int:
        """Recover only expired leases; do not touch unexpired running jobs."""
        timestamp = utc_time(now)
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            rows = self.conn.execute(
                """SELECT job_key, attempts, max_attempts FROM job_queue
                   WHERE state='RUNNING' AND lease_until<=?""",
                (timestamp,),
            ).fetchall()
            for row in rows:
                attempt = int(row["attempts"])
                max_attempts = int(row["max_attempts"])
                terminal = attempt >= max_attempts
                state = "FAILED" if terminal else "RETRY_WAIT"
                delay = min(5 * (2 ** (attempt - 1)), 300)
                when = timestamp if terminal else utc_time(now + timedelta(seconds=delay))
                self.conn.execute(
                    """UPDATE job_queue SET state=?, owner_id=NULL, lease_until=NULL,
                       available_at=?, updated_at=?, finished_at=?, last_error=?
                       WHERE job_key=?""",
                    (state, when, timestamp, timestamp if terminal else None,
                     "lease expired before completion", row["job_key"]),
                )
                self.conn.execute(
                    """UPDATE job_attempts SET ended_at=?, outcome=?, error_message=?
                       WHERE job_key=? AND attempt=?""",
                    (timestamp, state, "lease expired before completion",
                     row["job_key"], attempt),
                )
            self.conn.execute("COMMIT")
            return len(rows)
        except Exception:
            if self.conn.in_transaction:
                self.conn.execute("ROLLBACK")
            raise

    def get(self, key: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM job_queue WHERE job_key=?", (key,)
        ).fetchone()
        return dict(row) if row else None

    def latest(self, count: int = 20) -> list[dict[str, Any]]:
        if not 1 <= count <= 200:
            raise ValueError("count must be 1..200")
        rows = self.conn.execute(
            "SELECT * FROM job_queue ORDER BY created_at DESC, job_key DESC LIMIT ?",
            (count,),
        ).fetchall()
        return [dict(row) for row in rows]

    def counts(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT state, COUNT(*) AS n FROM job_queue GROUP BY state"
        ).fetchall()
        return {str(row["state"]): int(row["n"]) for row in rows}
