"""Observe Letta conversation compaction through its public API."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

from mabench.adapters.letta_adapter import LettaAdapter


def _structured_compaction_evidence(value: object) -> list[dict[str, object]]:
    """Collect explicit compaction/summary message records from an SDK response.

    This deliberately does not classify ordinary assistant prose as an event.
    Letta's response schema has changed across releases, so the detector keeps
    records whose structured type/key names identify summary or compaction.
    """
    found: list[dict[str, object]] = []

    def visit(item: object) -> None:
        if isinstance(item, dict):
            marker = " ".join(
                str(item.get(key, "")).lower()
                for key in (
                    "message_type", "type", "role", "name", "kind", "event",
                    "event_type",
                )
            )
            if "compaction" in marker or "summary" in marker:
                found.append(item)
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", default="phase3-letta-compaction")
    parser.add_argument("--messages", type=int, default=8)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.messages < 1:
        parser.error("--messages must be positive")

    adapter = LettaAdapter()
    process = psutil.Process(os.getpid())
    observations = []
    for index in range(1, args.messages + 1):
        started = time.perf_counter()
        response = adapter.send_message(
            f"Controlled compaction probe message {index}: preserve fact {index}.",
            args.session_id,
        )
        observations.append(
            {
                "message_index": index,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "rss_mb": round(process.memory_info().rss / 1e6, 3),
                "compaction_evidence": _structured_compaction_evidence(response),
                "response": response,
            }
        )
    before_messages = adapter.list_messages(args.session_id)
    compaction = adapter.compact_conversation(args.session_id)
    after_messages = adapter.list_messages(args.session_id)
    payload = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "framework": "letta",
        "session_id": args.session_id,
        "model_metadata": adapter.model_metadata(),
        "messages_sent": args.messages,
        "automatic_compaction_observed": any(
            item["compaction_evidence"] for item in observations
        ),
        "message_observations": observations,
        "message_count_before": len(before_messages),
        "message_count_after": len(after_messages),
        "compaction_response": compaction,
        "interpretation": "public_compaction_observed" if compaction else "no_response",
        "limitations": [
            "This explicitly invokes public compaction; it does not estimate an automatic threshold.",
            "Message-count change demonstrates compaction behavior, not a hidden trigger threshold.",
            "Reflection and sleep-time subsystem telemetry remain unobservable through this adapter.",
        ],
    }
    output = args.output or Path("results/Phase3/Letta") / f"phase3_compaction_{payload['run_id']}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output": str(output), "run_id": payload["run_id"]}, indent=2))


if __name__ == "__main__":
    main()
