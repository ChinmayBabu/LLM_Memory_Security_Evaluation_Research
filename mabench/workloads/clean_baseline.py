"""Clean baseline execution against a ``MemoryAdapter``."""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mabench.adapters.base import MemoryAdapter
from mabench.manifest import create_run_manifest
from mabench.metrics.logger import EventLogger
from mabench.metrics.quality import score_answer

from .fixtures import BASELINE_MEMORIES, BASELINE_QUERIES


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _retrieval_metrics(results: list[dict[str, Any]], gold_ids: list[str]) -> dict[str, float]:
    retrieved = [str(item.get("id")) for item in results if item.get("id") is not None]
    gold = set(gold_ids)
    hits_at_5 = len(set(retrieved[:5]) & gold)
    hits_at_10 = len(set(retrieved[:10]) & gold)
    first_rank = next((index + 1 for index, item in enumerate(retrieved) if item in gold), None)
    return {
        "recall_at_5": hits_at_5 / max(1, len(gold)),
        "recall_at_10": hits_at_10 / max(1, len(gold)),
        "precision_at_5": hits_at_5 / 5,
        "precision_at_10": hits_at_10 / 10,
        "mrr": 1.0 / first_rank if first_rank else 0.0,
        "ndcg": 1.0 / __import__("math").log2(first_rank + 1) if first_rank else 0.0,
    }


def run_clean_baseline(
    adapter: MemoryAdapter,
    *,
    session_id: str,
    results_dir: str | Path = "results",
    database_path: str | Path = "results/events.sqlite3",
    seed: int = 20260820,
    config: dict[str, Any] | None = None,
    models: dict[str, str] | None = None,
    system_name: str | None = None,
) -> dict[str, Any]:
    """Run the deterministic clean fixture and return summary statistics."""

    run_id, manifest_path = create_run_manifest(
        results_dir,
        system=system_name or getattr(adapter, "system_name", "unknown"),
        attack="clean",
        intensity="baseline",
        seed=seed,
        config=config or {},
        models=models or {},
    )
    database_path = Path(database_path)
    logger = EventLogger(database_path, run_id)

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO runs (run_id, system, attack, intensity, seed, started_at,
                              status, config_json, environment_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, system_name or getattr(adapter, "system_name", "unknown"), "clean", "baseline", seed,
             datetime.now(timezone.utc).isoformat(), "started",
             json.dumps(config or {}, sort_keys=True), "{}"),
        )

    fixture_to_memory_id: dict[str, str] = {}
    for item in BASELINE_MEMORIES:
        started = time.perf_counter()
        result = adapter.write(item["text"], session_id)
        stats = adapter.stats()
        logger.log(
            "write",
            write_latency_ms=(time.perf_counter() - started) * 1000,
            entry_count=stats.get("entry_count"),
            storage_bytes=stats.get("storage_bytes"),
            metadata={"fixture_id": item["id"], "adapter_result": result},
        )
        for added in result.get("results", []) if isinstance(result, dict) else []:
            if added.get("event") in {"ADD", "UPDATE"} and added.get("id"):
                added_text = str(added.get("memory", ""))
                if _normalize_text(added_text) == _normalize_text(item["text"]):
                    fixture_to_memory_id[item["id"]] = str(added["id"])
                elif item["id"] not in fixture_to_memory_id:
                    fixture_to_memory_id[item["id"]] = str(added["id"])

    query_summaries = []
    for item in BASELINE_QUERIES:
        started = time.perf_counter()
        results = adapter.query(item["question"], session_id, k=10)
        query_latency_ms = (time.perf_counter() - started) * 1000
        gold_memory_ids = [
            fixture_to_memory_id[fixture_id]
            for fixture_id in item["gold_memory_ids"]
            if fixture_id in fixture_to_memory_id
        ]
        metrics = _retrieval_metrics(results, gold_memory_ids)
        logger.log(
            "query",
            query_latency_ms=query_latency_ms,
            **metrics,
            metadata={
                "query_id": item["id"],
                "gold_fixture_ids": item["gold_memory_ids"],
                "gold_memory_ids": gold_memory_ids,
                "results": results,
            },
        )

        started = time.perf_counter()
        answer = adapter.answer(item["question"], session_id)
        answer_correct = score_answer(answer, item.get("answer_keywords", []))
        logger.log(
            "answer",
            answer_latency_ms=(time.perf_counter() - started) * 1000,
            answer_correct=answer_correct,
            metadata={
                "query_id": item["id"],
                "answer": answer,
                "answer_keywords": item.get("answer_keywords", []),
            },
        )
        query_summaries.append({"query_id": item["id"], "answer_correct": answer_correct, **metrics})

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE runs SET finished_at = ?, status = ? WHERE run_id = ?",
            (datetime.now(timezone.utc).isoformat(), "completed", run_id),
        )

    return {
        "run_id": run_id,
        "manifest_path": str(manifest_path),
        "database_path": str(database_path),
        "queries": query_summaries,
    }
