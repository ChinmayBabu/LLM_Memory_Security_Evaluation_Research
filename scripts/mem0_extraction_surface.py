"""Measure Mem0 extraction-path cost with the shared pressure/clean workload."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

from mabench.adapters.mem0_adapter import Mem0Adapter
from mabench.attacks.reflection_loop import (
    estimate_input_tokens,
    make_clean_message,
    make_pressure_message,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--store-path", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--topics-per-round", type=int, default=1)
    parser.add_argument("--message-length", type=int, default=120)
    parser.add_argument("--pattern", choices=("pressure", "clean"), default="pressure")
    parser.add_argument("--llm-model", default="qwen2.5:1.5b-instruct")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    adapter = Mem0Adapter(
        store_path=args.store_path,
        llm_model=args.llm_model,
        infer_on_write=True,
    )
    observations = []
    started_run = time.perf_counter()
    for index in range(1, args.rounds + 1):
        text = (
            make_pressure_message(index, args.topics_per_round, args.message_length)
            if args.pattern == "pressure"
            else make_clean_message(index, args.topics_per_round, args.message_length)
        )
        started = time.perf_counter()
        error = None
        result = None
        try:
            result = adapter.write(text, args.session_id)
        except Exception as exc:  # preserve failed requests in the artifact
            error = f"{type(exc).__name__}: {str(exc)[:500]}"
        observations.append({
            "round_index": index,
            "input_tokens_estimate": estimate_input_tokens(text),
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "result": result,
            "error": error,
        })
    payload = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "phase": "mem0-extraction-surface",
        "framework": "mem0",
        "configuration": vars(args),
        "model_metadata": adapter.model_metadata(),
        "duration_s": round(time.perf_counter() - started_run, 3),
        "observations": observations,
        "summary": {
            "completed": sum(item["error"] is None for item in observations),
            "failed": sum(item["error"] is not None for item in observations),
            "mean_latency_ms": sum(item["latency_ms"] for item in observations) / max(1, len(observations)),
            "entry_count": adapter.stats().get("entry_count"),
        },
        "resource_sample": {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "rss_bytes": psutil.Process().memory_info().rss,
        },
        "interpretation": "Mem0 synchronous extraction-path cost; not Letta sleeptime reflection.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output": str(args.output), **payload["summary"]}, indent=2))


if __name__ == "__main__":
    main()
