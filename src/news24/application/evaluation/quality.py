"""Source-span golden evaluation and transparent local readiness diagnostics."""

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from news24.application.intelligence.service import _evidence_status
from news24.infrastructure.sqlite.database import SQLiteNewsStore

ALGORITHM_VERSION = "exact-span-v1"


def evaluate_evidence(
    store: SQLiteNewsStore,
    dataset: str | Path,
    *,
    record: bool = True,
) -> dict[str, Any]:
    """Compare exact span verdicts to user-controlled golden examples.

    This measures lexical quotation correctness ONLY. No inference about the
    truth of a model claim or downstream investment outcome is permitted.
    """
    raw = Path(dataset).read_bytes()
    content = json.loads(raw)
    if not isinstance(content, dict) or not isinstance(content.get("cases"), list):
        raise ValueError("golden dataset must have a list of cases")
    cases = content["cases"]
    if not cases:
        raise ValueError("golden dataset must not be empty")
    verdicts = {"TEXT_MATCH_ONLY", "NOT_FOUND", "AMBIGUOUS"}
    confusion: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"case {i} must be object")
        actual_text = case.get("text")
        quote = case.get("quote")
        expected = case.get("verdict")
        if not isinstance(actual_text, str) or not isinstance(quote, str):
            raise ValueError(f"case {i} needs text and quote strings")
        if not isinstance(expected, str) or expected not in verdicts:
            raise ValueError(f"case {i} has unsupported expected verdict")
        observed, begin, end = _evidence_status(actual_text, quote)
        if observed == "TEXT_MATCH_ONLY" and actual_text[begin:end] != quote:
            observed = "NOT_FOUND"
        confusion[f"{expected}->{observed}"] += 1
        if expected != observed:
            failures.append({"index": i, "expected": expected, "observed": observed})
    passed = len(cases) - len(failures)
    digest = hashlib.sha256(raw).hexdigest()
    key = hashlib.sha256((digest + ALGORITHM_VERSION).encode("ascii")).hexdigest()
    result: dict[str, Any] = {
        "run_id": key,
        "dataset_sha256": digest,
        "algorithm": ALGORITHM_VERSION,
        "cases": len(cases),
        "passed": passed,
        "failed": len(failures),
        "confusion": dict(confusion),
        "failures": failures[:100],
        "metric_scope": "lexical exact-match only, not semantic claim truth",
        "ok": passed == len(cases),
    }
    if record:
        store.migrate()
        store.conn.execute(
            """INSERT OR IGNORE INTO evaluation_runs
               (run_id,dataset_sha256,algorithm,total_cases,passed_cases,
                metrics_json,evaluated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                key, digest, ALGORITHM_VERSION, len(cases), passed,
                json.dumps(result, ensure_ascii=False, sort_keys=True),
                datetime.now(UTC).isoformat(),
            ),
        )
    return result


def readiness(store: SQLiteNewsStore) -> dict[str, Any]:
    """Never represent offline checks as production network/model validation."""
    store.migrate()
    checks: dict[str, Any] = {}
    checks["schema_version"] = int(store.conn.execute("PRAGMA user_version").fetchone()[0])
    checks["failed_jobs"] = int(store.conn.execute(
        "SELECT COUNT(*) FROM job_queue WHERE state='FAILED'"
    ).fetchone()[0])
    checks["incomplete_ingestion_runs"] = int(store.conn.execute(
        "SELECT COUNT(*) FROM ingestion_runs WHERE status='INCOMPLETE'"
    ).fetchone()[0])
    checks["evidence_eval_runs"] = int(store.conn.execute(
        "SELECT COUNT(*) FROM evaluation_runs"
    ).fetchone()[0])
    checks["latest_sina_probe"] = store.conn.execute(
        """SELECT status FROM source_probes WHERE source='sina_7x24'
           ORDER BY checked_at DESC, probe_id DESC LIMIT 1"""
    ).fetchone()
    checks["latest_sina_probe"] = (
        str(checks["latest_sina_probe"][0])
        if checks["latest_sina_probe"] is not None else "NOT_RUN"
    )
    return {
        "readiness": "NOT_PRODUCTION_VERIFIED",
        "checks": checks,
        "required_external_gates": [
            "authorized live Sina pagination and freshness",
            "live configured model response and cost budget",
            "human reviewed semantic factual accuracy",
            "live security and browser interaction testing",
        ],
    }
