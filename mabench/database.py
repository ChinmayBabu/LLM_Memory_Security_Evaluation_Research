"""SQLite initialization for per-run event logging."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def initialize_database(database_path: str | Path, schema_path: str | Path = "schema.sql") -> None:
    """Create the benchmark database and apply the checked-in schema."""

    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    schema = Path(schema_path).read_text(encoding="utf-8")
    with sqlite3.connect(database_path) as connection:
        connection.executescript(schema)
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(events)")
        }
        if "answer_latency_ms" not in columns:
            connection.execute("ALTER TABLE events ADD COLUMN answer_latency_ms REAL")
