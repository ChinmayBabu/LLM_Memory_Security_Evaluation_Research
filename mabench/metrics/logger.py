"""Per-event SQLite logging for benchmark runs."""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

from mabench.database import initialize_database


class EventLogger:
    """Write normalized event records while preserving extra metadata as JSON."""

    def __init__(self, database_path: str | Path, run_id: str) -> None:
        self.database_path = Path(database_path)
        initialize_database(self.database_path)
        self.run_id = run_id
        self._event_index = 0
        self._start = time.perf_counter()

    def log(self, event_type: str, **fields: Any) -> int:
        event_index = self._event_index
        self._event_index += 1
        known = {
            "cpu_pct",
            "rss_mb",
            "write_latency_ms",
            "query_latency_ms",
            "answer_latency_ms",
            "storage_bytes",
            "entry_count",
            "reflection_triggered",
            "compression_triggered",
            "attacker_tokens",
            "system_tokens",
            "recall_at_5",
            "recall_at_10",
            "precision_at_5",
            "precision_at_10",
            "mrr",
            "ndcg",
            "answer_correct",
        }
        process = psutil.Process()
        record = {key: fields.pop(key, None) for key in known}
        record["cpu_pct"] = record["cpu_pct"] if record["cpu_pct"] is not None else psutil.cpu_percent()
        record["rss_mb"] = record["rss_mb"] if record["rss_mb"] is not None else process.memory_info().rss / 1e6
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO events (
                    run_id, event_index, event_type, t_monotonic_s, recorded_at,
                    cpu_pct, rss_mb, write_latency_ms, query_latency_ms,
                    answer_latency_ms,
                    storage_bytes, entry_count, reflection_triggered,
                    compression_triggered, attacker_tokens, system_tokens,
                    recall_at_5, recall_at_10, precision_at_5, precision_at_10,
                    mrr, ndcg, answer_correct, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.run_id,
                    event_index,
                    event_type,
                    time.perf_counter() - self._start,
                    datetime.now(timezone.utc).isoformat(),
                    record["cpu_pct"],
                    record["rss_mb"],
                    record["write_latency_ms"],
                    record["query_latency_ms"],
                    record["answer_latency_ms"],
                    record["storage_bytes"],
                    record["entry_count"],
                    record["reflection_triggered"],
                    record["compression_triggered"],
                    record["attacker_tokens"],
                    record["system_tokens"],
                    record["recall_at_5"],
                    record["recall_at_10"],
                    record["precision_at_5"],
                    record["precision_at_10"],
                    record["mrr"],
                    record["ndcg"],
                    record["answer_correct"],
                    json.dumps(fields, sort_keys=True, default=str),
                ),
            )
        return event_index
