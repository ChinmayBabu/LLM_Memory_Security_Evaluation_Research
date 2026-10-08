"""Validate model and conversation-event telemetry before reflection attacks."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from mabench.adapters.letta_adapter import LettaAdapter


def _messages(response: Any) -> list[dict[str, Any]]:
    if not isinstance(response, dict):
        return []
    values = response.get("messages", response.get("data", []))
    return values if isinstance(values, list) else []


def _events(response: Any) -> list[dict[str, Any]]:
    records = []
    for item in _messages(response):
        if not isinstance(item, dict):
            continue
        message_type = item.get("message_type")
        if message_type in {"event_message", "summary_message"}:
            records.append(item)
    return records


def _proxy_events(base_url: str) -> list[dict[str, Any]]:
    proxy_url = base_url.rstrip("/")
    response = httpx.get(f"{proxy_url}/telemetry/events", timeout=10.0)
    response.raise_for_status()
    payload = response.json()
    return payload.get("events", [])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", default="phase3-reflection-instrumentation")
    parser.add_argument("--messages", type=int, default=8)
    parser.add_argument("--proxy-url", default="http://127.0.0.1:8787")
    parser.add_argument("--settle-seconds", type=float, default=5.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.messages < 1:
        parser.error("--messages must be positive")

    try:
        httpx.delete(f"{args.proxy_url.rstrip('/')}/telemetry/events", timeout=10.0).raise_for_status()
        proxy_available = True
    except Exception as exc:
        proxy_available = False
        proxy_error = f"{type(exc).__name__}: {exc}"

    adapter = LettaAdapter()
    observations = []
    for index in range(1, args.messages + 1):
        correlation_id = f"{args.session_id}-{index}-{uuid.uuid4().hex[:8]}"
        started = time.perf_counter()
        response = adapter.conversation_turn(
            f"Instrumentation validation message {index}: preserve controlled fact {index}.",
            args.session_id,
            include_compaction_messages=True,
            correlation_id=correlation_id,
        )
        observations.append({
            "message_index": index,
            "correlation_id": correlation_id,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "event_messages": _events(response),
            "usage": response.get("usage", {}) if isinstance(response, dict) else {},
            "response": response,
        })

    # Sleeptime runs are asynchronous and may begin after the foreground API
    # response. Allow them to finish before collecting proxy telemetry.
    if args.settle_seconds > 0:
        time.sleep(args.settle_seconds)
    proxy_events = []
    if proxy_available:
        proxy_events = _proxy_events(args.proxy_url)
    usage_events = [item for item in proxy_events if isinstance(item.get("usage"), dict)]
    total_tokens = sum(int(item["usage"].get("total_tokens", 0)) for item in usage_events)
    event_messages = [event for item in observations for event in item["event_messages"]]
    letta_usage = [item["usage"] for item in observations if item["usage"]]
    letta_total_tokens = sum(int(item.get("total_tokens", 0)) for item in letta_usage)
    reflection_proxy_events = [
        item for item in proxy_events
        if item.get("request_class") == "sleeptime_reflection"
    ]
    reflection_proxy_tokens = sum(
        int(item.get("usage", {}).get("total_tokens", 0))
        for item in reflection_proxy_events
    )
    reflection_telemetry_ready = bool(
        reflection_proxy_events and reflection_proxy_tokens > 0
    )
    payload = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "framework": "letta",
        "session_id": args.session_id,
        "model_metadata": adapter.model_metadata(),
        "messages_sent": args.messages,
        "observations": observations,
        "proxy_telemetry_available": proxy_available,
        "proxy_error": None if proxy_available else proxy_error,
        "proxy_events": proxy_events,
        "structured_compaction_events": event_messages,
        "letta_usage_telemetry_available": bool(letta_usage and letta_total_tokens > 0),
        "token_telemetry_available": bool(
            (usage_events and total_tokens > 0) or letta_total_tokens > 0
        ),
        "total_model_tokens": total_tokens or letta_total_tokens,
        "reflection_proxy_events": reflection_proxy_events,
        "reflection_proxy_tokens": reflection_proxy_tokens,
        "reflection_telemetry_available": reflection_telemetry_ready or any(
            "reflection" in json.dumps(event).lower() for event in event_messages
        ),
        "gate_status": (
            "reflection_telemetry_ready"
            if proxy_available and total_tokens > 0 and reflection_telemetry_ready
            else "instrumentation_incomplete"
        ),
        "limitations": [
            "Model-proxy token telemetry identifies model requests but does not by itself prove that a request is reflection work.",
            "Compaction event messages are separate from sleep-time reflection events.",
            "A reflection attack must not be run as a claimed result unless gate_status is reflection_telemetry_ready.",
        ],
    }
    output = args.output or Path("results/Phase3/Letta") / f"reflection_instrumentation_{payload['run_id']}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output": str(output), "gate_status": payload["gate_status"]}, indent=2))


if __name__ == "__main__":
    main()
