
CREATE TABLE IF NOT EXISTS job_queue (
    job_key TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('collect', 'report', 'probe', 'analyze')),
    payload_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('QUEUED','RUNNING','RETRY_WAIT','SUCCEEDED','FAILED')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts INTEGER NOT NULL CHECK (max_attempts BETWEEN 1 AND 10),
    available_at TEXT NOT NULL,
    lease_until TEXT,
    owner_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    finished_at TEXT,
    last_error TEXT,
    result_json TEXT
);
CREATE INDEX IF NOT EXISTS ix_job_ready ON job_queue(state, available_at);

CREATE TABLE IF NOT EXISTS job_attempts (
    job_key TEXT NOT NULL REFERENCES job_queue(job_key),
    attempt INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    outcome TEXT CHECK (outcome IN ('SUCCEEDED','FAILED','RETRY_WAIT')),
    error_message TEXT,
    PRIMARY KEY(job_key, attempt)
);

CREATE TABLE IF NOT EXISTS job_schedules (
    schedule_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('collect','report','probe')),
    payload_json TEXT NOT NULL,
    cadence TEXT NOT NULL CHECK(cadence IN ('interval','daily')),
    interval_seconds INTEGER,
    local_time TEXT,
    timezone TEXT NOT NULL,
    next_due_at TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1))
);
CREATE INDEX IF NOT EXISTS ix_schedule_due ON job_schedules(enabled, next_due_at);

CREATE TABLE IF NOT EXISTS report_runs (
    report_key TEXT PRIMARY KEY,
    report_date TEXT NOT NULL,
    timezone TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    news_count INTEGER NOT NULL,
    completeness TEXT NOT NULL DEFAULT 'UNVERIFIED',
    markdown TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_revisions (
    report_key TEXT NOT NULL REFERENCES report_runs(report_key),
    revision INTEGER NOT NULL,
    markdown TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    PRIMARY KEY(report_key, revision)
);

CREATE TABLE IF NOT EXISTS source_probes (
    probe_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('OK','EMPTY','STALE','ERROR')),
    articles_seen INTEGER,
    newest_published_at TEXT,
    age_seconds REAL,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS ix_source_probes_source ON source_probes(source, checked_at DESC);
