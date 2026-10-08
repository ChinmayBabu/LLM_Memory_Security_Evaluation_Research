"""Run a bounded concurrent reflection-cost availability experiment."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import psutil

from mabench.adapters.letta_adapter import LettaAdapter
from mabench.attacks.availability import run_concurrent_requests, summarize_requests
from mabench.attacks.reflection_loop import make_clean_message, make_pressure_message


def proxy_request(proxy_url: str, method: str, path: str) -> dict[str, Any]:
    response = httpx.request(method, f"{proxy_url.rstrip('/')}{path}", timeout=10.0)
    response.raise_for_status()
    return response.json()


def sample_host(stop: threading.Event, samples: list[dict[str, Any]], interval_s: float) -> None:
    process = psutil.Process(os.getpid())
    while not stop.is_set():
        samples.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cpu_percent": psutil.cpu_percent(interval=None),
            "rss_bytes": process.memory_info().rss,
        })
        stop.wait(interval_s)


def make_jobs(condition: str, sessions: int, rounds: int, rate: int) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for round_index in range(1, rounds + 1):
        for session_index in range(sessions):
            role = "attacker" if session_index == 0 and condition != "baseline" else "legitimate"
            session_id = f"phase3-5-{condition}-user-{session_index}"
            if role == "attacker":
                text = (make_pressure_message(round_index, 5)
                        if condition == "pressure"
                        else make_clean_message(round_index, 5))
            else:
                text = f"Routine legitimate request round {round_index}: summarize the current session state for user {session_index}."
            for repetition in range(rate if role == "attacker" else 1):
                jobs.append({
                    "request_id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "role": role,
                    "round_index": round_index,
                    "text": text,
                    "repetition": repetition,
                })
    return jobs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", choices=("baseline", "pressure", "clean"), required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--legitimate-sessions", type=int, default=4)
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--attacker-rate", type=int, default=1)
    parser.add_argument("--request-timeout", type=float, default=120.0)
    parser.add_argument("--settle-seconds", type=float, default=10.0)
    parser.add_argument("--sample-interval", type=float, default=1.0)
    parser.add_argument("--proxy-url", default="http://127.0.0.1:8787")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.legitimate_sessions < 1 or args.rounds < 1 or args.attacker_rate < 1:
        raise SystemExit("sessions, rounds, and attacker-rate must be positive")

    proxy_request(args.proxy_url, "DELETE", "/telemetry/events")
    jobs = make_jobs(args.condition, args.legitimate_sessions + (0 if args.condition == "baseline" else 1), args.rounds, args.attacker_rate)
    adapters: dict[str, LettaAdapter] = {}
    adapters_lock = threading.Lock()

    def request(job: dict[str, Any]) -> None:
        with adapters_lock:
            adapter = adapters.setdefault(job["session_id"], LettaAdapter())
        job["started_perf"] = time.perf_counter()
        adapter.conversation_turn(
            job["text"], job["session_id"],
            include_compaction_messages=True,
            correlation_id=f"phase3-5-{args.session_id}-{job['request_id']}",
        )

    samples: list[dict[str, Any]] = []
    stop = threading.Event()
    sampler = threading.Thread(target=sample_host, args=(stop, samples, args.sample_interval), daemon=True)
    started = time.perf_counter()
    sampler.start()
    try:
        requests = run_concurrent_requests(
            jobs, request_fn=request, max_workers=len(jobs), timeout_s=args.request_timeout
        )
    finally:
        stop.set()
        sampler.join(timeout=2.0)
    duration_s = time.perf_counter() - started
    if args.settle_seconds > 0:
        time.sleep(args.settle_seconds)
    telemetry_error = None
    try:
        proxy_events = proxy_request(args.proxy_url, "GET", "/telemetry/events").get("events", [])
    except Exception as exc:
        proxy_events = []
        telemetry_error = f"{type(exc).__name__}: {str(exc)[:500]}"
    reflection_events = [event for event in proxy_events if event.get("request_class") == "sleeptime_reflection"]
    reflection_tokens = sum(int(event.get("usage", {}).get("total_tokens", 0)) for event in reflection_events)
    summary = summarize_requests(requests, duration_s)
    payload = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "phase": "3.5",
        "framework": "letta",
        "attack": "reflection_cost_availability",
        "configuration": vars(args),
        "model_metadata": LettaAdapter().model_metadata(),
        "duration_s": round(duration_s, 3),
        "request_summary": summary,
        "requests": requests,
        "host_samples": samples,
        "proxy_events": proxy_events,
        "reflection_event_count": len(reflection_events),
        "reflection_tokens": reflection_tokens,
        "telemetry_gate": "reflection_telemetry_ready" if reflection_events and reflection_tokens > 0 else "incomplete",
        "telemetry_error": telemetry_error,
        "limitations": [
            "This bounded local experiment does not establish impact against external services.",
            "Attacker and legitimate request counts are reported separately only through per-request role labels.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "requests": summary["requests_total"],
        "completed": summary["requests_completed"],
        "p95_ms": summary["latency_ms"]["p95"],
        "error_rate": summary["error_rate"],
        "reflection_events": len(reflection_events),
        "reflection_tokens": reflection_tokens,
    }, indent=2))


if __name__ == "__main__":
    main()
