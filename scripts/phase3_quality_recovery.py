"""Measure retrieval quality before, after, and during recovery from reflection pressure."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from mabench.adapters.letta_adapter import LettaAdapter
from mabench.attacks.reflection_loop import reflection_loop_attack
from mabench.workloads.clean_baseline import _retrieval_metrics
from mabench.workloads.fixtures import BASELINE_MEMORIES, BASELINE_QUERIES
from mabench.metrics.quality import score_answer


def seed_memories(adapter: LettaAdapter, session_id: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in BASELINE_MEMORIES:
        result = adapter.write(item["text"], session_id)
        values = result.get("results", []) if isinstance(result, dict) else []
        if values and values[0].get("id"):
            mapping[item["id"]] = str(values[0]["id"])
    return mapping


def measure_quality(adapter: LettaAdapter, session_id: str, mapping: dict[str, str], *, include_answers: bool) -> dict:
    rows = []
    for item in BASELINE_QUERIES:
        results = adapter.query(item["question"], session_id, k=10)
        gold_ids = [mapping[key] for key in item["gold_memory_ids"] if key in mapping]
        row = {"query_id": item["id"], **_retrieval_metrics(results, gold_ids)}
        if include_answers:
            answer = adapter.answer(item["question"], session_id)
            row["answer_correct"] = score_answer(answer, item.get("answer_keywords", []))
        rows.append(row)
    metrics = {
        key: sum(row[key] for row in rows) / len(rows)
        for key in ("recall_at_5", "recall_at_10", "precision_at_5", "precision_at_10", "mrr", "ndcg")
    }
    metrics["queries"] = rows
    if include_answers:
        metrics["answer_correct"] = sum(row["answer_correct"] for row in rows) / len(rows)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--topics-per-round", type=int, default=5)
    parser.add_argument("--recovery-seconds", default="60,300")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    adapter = LettaAdapter()
    mapping = seed_memories(adapter, args.session_id)
    checkpoints = [int(value) for value in args.recovery_seconds.split(",") if value.strip()]
    measurements = [{"stage": "before_attack", "seconds_after_attack": 0, "metrics": measure_quality(adapter, args.session_id, mapping, include_answers=True)}]
    attack_started = datetime.now(timezone.utc).isoformat()
    attack = reflection_loop_attack(
        adapter,
        args.session_id,
        rounds=args.rounds,
        topics_per_round=args.topics_per_round,
        pattern="pressure",
    )
    measurements.append({"stage": "immediately_after_attack", "seconds_after_attack": 0, "metrics": measure_quality(adapter, args.session_id, mapping, include_answers=True)})
    for seconds in checkpoints:
        time.sleep(seconds)
        measurements.append({"stage": "recovery", "seconds_after_attack": seconds, "metrics": measure_quality(adapter, args.session_id, mapping, include_answers=False)})
    payload = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "framework": "letta",
        "attack": "reflection_loop_quality_recovery",
        "session_id": args.session_id,
        "model_metadata": adapter.model_metadata(),
        "configuration": {"rounds": args.rounds, "topics_per_round": args.topics_per_round, "recovery_checkpoints_s": checkpoints},
        "seeded_memory_count": len(mapping),
        "attack_started_at": attack_started,
        "attack_workload": attack,
        "measurements": measurements,
        "limitations": [
            "This pilot measures retrieval quality; answer correctness is not included.",
            "Recovery waits are idle periods with no legitimate traffic.",
            "Reflection activity is correlated through validated sleeptime proxy telemetry in separate attack artifacts.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "seeded_memories": len(mapping), "measurements": len(measurements)}, indent=2))


if __name__ == "__main__":
    main()
