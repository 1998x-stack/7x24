
CREATE TABLE IF NOT EXISTS analysis_results (
    analysis_key TEXT PRIMARY KEY,
    uid TEXT NOT NULL REFERENCES news(uid) ON DELETE CASCADE,
    revision_hash TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    prompt_sha256 TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('ACCEPTED','PARTIAL','REJECTED')),
    sentiment TEXT CHECK(sentiment IN ('positive','negative','neutral','unknown')),
    output_json TEXT NOT NULL,
    response_id TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    created_at TEXT NOT NULL,
    CHECK(input_tokens IS NULL OR input_tokens >= 0),
    CHECK(output_tokens IS NULL OR output_tokens >= 0)
);
CREATE INDEX IF NOT EXISTS ix_analysis_uid ON analysis_results(uid, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_analysis_version ON analysis_results(
    uid, revision_hash, model, prompt_version
);

CREATE TABLE IF NOT EXISTS evidence_spans (
    analysis_key TEXT NOT NULL REFERENCES analysis_results(analysis_key)
        ON DELETE CASCADE,
    claim_index INTEGER NOT NULL,
    statement TEXT NOT NULL,
    quote TEXT NOT NULL,
    span_start INTEGER,
    span_end INTEGER,
    verdict TEXT NOT NULL CHECK(verdict IN ('TEXT_MATCH_ONLY','NOT_FOUND','AMBIGUOUS')),
    PRIMARY KEY(analysis_key, claim_index),
    CHECK(
      (verdict='TEXT_MATCH_ONLY' AND span_start >= 0 AND span_end > span_start)
      OR (verdict<>'TEXT_MATCH_ONLY' AND span_start IS NULL AND span_end IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS event_clusters (
    event_key TEXT PRIMARY KEY,
    local_day TEXT NOT NULL,
    normalized_quote TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'CANDIDATE'
       CHECK(status='CANDIDATE'),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS event_members (
    event_key TEXT NOT NULL REFERENCES event_clusters(event_key) ON DELETE CASCADE,
    analysis_key TEXT NOT NULL,
    claim_index INTEGER NOT NULL,
    uid TEXT NOT NULL REFERENCES news(uid) ON DELETE CASCADE,
    PRIMARY KEY(event_key, analysis_key, claim_index),
    FOREIGN KEY(analysis_key, claim_index)
        REFERENCES evidence_spans(analysis_key, claim_index) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_event_members_uid ON event_members(uid);
