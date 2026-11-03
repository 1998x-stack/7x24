
CREATE TABLE IF NOT EXISTS news (
    uid TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    title TEXT,
    content_raw TEXT NOT NULL,
    content_text TEXT NOT NULL,
    published_at TEXT,
    updated_at TEXT,
    first_fetched_at TEXT NOT NULL,
    last_fetched_at TEXT NOT NULL,
    source_url TEXT,
    content_hash TEXT NOT NULL,
    revision_hash TEXT NOT NULL,
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0,1)),
    is_repeated INTEGER NOT NULL DEFAULT 0 CHECK (is_repeated IN (0,1)),
    raw_json TEXT NOT NULL,
    article_json TEXT NOT NULL,
    UNIQUE(source, source_id)
);

CREATE INDEX IF NOT EXISTS ix_news_publish ON news(published_at DESC);
CREATE INDEX IF NOT EXISTS ix_news_source ON news(source, source_id);

CREATE TABLE IF NOT EXISTS news_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT NOT NULL REFERENCES news(uid) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    revision_hash TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE(uid, version)
);

CREATE TABLE IF NOT EXISTS news_categories (
    uid TEXT NOT NULL REFERENCES news(uid) ON DELETE CASCADE,
    category TEXT NOT NULL,
    PRIMARY KEY(uid, category)
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    category TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL CHECK (
        status IN ('RUNNING','SUCCEEDED','NO_CHANGES','INCOMPLETE','FAILED')
    ),
    pages_fetched INTEGER NOT NULL DEFAULT 0,
    articles_seen INTEGER NOT NULL DEFAULT 0,
    articles_inserted INTEGER NOT NULL DEFAULT 0,
    articles_revised INTEGER NOT NULL DEFAULT 0,
    checkpoint_before TEXT,
    checkpoint_after TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS ix_ingestion_runs_status
    ON ingestion_runs(status, started_at DESC);

CREATE TABLE IF NOT EXISTS source_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES ingestion_runs(run_id),
    source TEXT NOT NULL,
    category TEXT NOT NULL,
    page INTEGER NOT NULL,
    fetched_at TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(run_id, page)
);

CREATE TABLE IF NOT EXISTS source_checkpoints (
    source TEXT NOT NULL,
    category TEXT NOT NULL,
    last_seen_id TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES ingestion_runs(run_id),
    PRIMARY KEY(source, category)
);

CREATE VIRTUAL TABLE IF NOT EXISTS news_fts USING fts5(
    title, content_text,
    content='news',
    content_rowid='rowid',
    tokenize='trigram'
);
CREATE TRIGGER IF NOT EXISTS news_insert AFTER INSERT ON news BEGIN
    INSERT INTO news_fts(rowid, title, content_text)
    VALUES (new.rowid, new.title, new.content_text);
END;
CREATE TRIGGER IF NOT EXISTS news_delete AFTER DELETE ON news BEGIN
    INSERT INTO news_fts(news_fts, rowid, title, content_text)
    VALUES ('delete', old.rowid, old.title, old.content_text);
END;
CREATE TRIGGER IF NOT EXISTS news_update AFTER UPDATE OF title, content_text ON news BEGIN
    INSERT INTO news_fts(news_fts, rowid, title, content_text)
    VALUES ('delete', old.rowid, old.title, old.content_text);
    INSERT INTO news_fts(rowid, title, content_text)
    VALUES (new.rowid, new.title, new.content_text);
END;
