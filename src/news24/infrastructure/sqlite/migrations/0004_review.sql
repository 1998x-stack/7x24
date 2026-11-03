
-- Immutable operator review history. No database row or model output is overwritten.
CREATE TABLE IF NOT EXISTS claim_review_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_key TEXT NOT NULL,
    claim_index INTEGER NOT NULL,
    review_version INTEGER NOT NULL CHECK(review_version > 0),
    source_revision TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK(verdict IN ('SUPPORTED_BY_TEXT','NOT_SUPPORTED_BY_TEXT','NEEDS_INVESTIGATION')),
    reviewer TEXT NOT NULL,
    reason TEXT NOT NULL CHECK(length(reason) BETWEEN 8 AND 1000),
    reviewed_at TEXT NOT NULL,
    FOREIGN KEY(analysis_key, claim_index)
      REFERENCES evidence_spans(analysis_key, claim_index),
    UNIQUE(analysis_key, claim_index, review_version)
);
CREATE INDEX IF NOT EXISTS ix_claim_review_latest
    ON claim_review_log(analysis_key, claim_index, review_version DESC);

CREATE TABLE IF NOT EXISTS event_review_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_key TEXT NOT NULL REFERENCES event_clusters(event_key),
    review_version INTEGER NOT NULL CHECK(review_version > 0),
    verdict TEXT NOT NULL CHECK(verdict IN ('RELATED','NOT_RELATED','NEEDS_INVESTIGATION')),
    reviewer TEXT NOT NULL,
    reason TEXT NOT NULL CHECK(length(reason) BETWEEN 8 AND 1000),
    reviewed_at TEXT NOT NULL,
    UNIQUE(event_key, review_version)
);
CREATE INDEX IF NOT EXISTS ix_event_review_latest
    ON event_review_log(event_key, review_version DESC);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    run_id TEXT PRIMARY KEY,
    dataset_sha256 TEXT NOT NULL,
    algorithm TEXT NOT NULL,
    total_cases INTEGER NOT NULL CHECK(total_cases >= 0),
    passed_cases INTEGER NOT NULL CHECK(passed_cases >= 0),
    metrics_json TEXT NOT NULL,
    evaluated_at TEXT NOT NULL
);
