PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    system TEXT NOT NULL,
    attack TEXT NOT NULL,
    intensity TEXT NOT NULL,
    seed INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'started',
    config_json TEXT NOT NULL,
    environment_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    event_index INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    t_monotonic_s REAL NOT NULL,
    recorded_at TEXT NOT NULL,
    cpu_pct REAL,
    rss_mb REAL,
    write_latency_ms REAL,
    query_latency_ms REAL,
    answer_latency_ms REAL,
    storage_bytes INTEGER,
    entry_count INTEGER,
    reflection_triggered INTEGER,
    compression_triggered INTEGER,
    attacker_tokens INTEGER,
    system_tokens INTEGER,
    recall_at_5 REAL,
    recall_at_10 REAL,
    precision_at_5 REAL,
    precision_at_10 REAL,
    mrr REAL,
    ndcg REAL,
    answer_correct INTEGER,
    metadata_json TEXT,
    UNIQUE(run_id, event_index),
    CHECK(reflection_triggered IS NULL OR reflection_triggered IN (0, 1)),
    CHECK(compression_triggered IS NULL OR compression_triggered IN (0, 1)),
    CHECK(answer_correct IS NULL OR answer_correct IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_events_run_time ON events(run_id, t_monotonic_s);
CREATE INDEX IF NOT EXISTS idx_runs_experiment ON runs(system, attack, intensity, seed);
