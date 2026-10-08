"""Measure reflection cost across a bounded workload/configuration surface."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from mabench.adapters.letta_adapter import LettaAdapter
from mabench.attacks.reflection_loop import reflection_loop_attack


def proxy_request(proxy_url: str, method: str, path: str) -> dict:
    response = httpx.request(method, f"{proxy_url.rstrip('/')}{path}", timeout=10.0)
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--topics-per-round", type=int, default=5)
    parser.add_argument("--message-length", type=int)
    parser.add_argument("--pattern", choices=("pressure", "clean"), default="pressure")
    parser.add_argument("--sleeptime-frequency", type=int)
    parser.add_argument("--model")
    parser.add_argument("--settle-seconds", type=float, default=10.0)
    parser.add_argument("--proxy-url", default="http://127.0.0.1:8787")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.rounds < 1 or args.topics_per_round < 1:
        raise SystemExit("rounds and topics-per-round must be positive")

    proxy_request(args.proxy_url, "DELETE", "/telemetry/events")
    adapter = LettaAdapter(llm_model=args.model, sleeptime_agent_frequency=args.sleeptime_frequency)
    started = time.perf_counter()
    attack = reflection_loop_attack(
        adapter,
        args.session_id,
        rounds=args.rounds,
        topics_per_round=args.topics_per_round,
        pattern=args.pattern,
        message_length=args.message_length,
    )
    attack_duration_s = time.perf_counter() - started
    if args.settle_seconds > 0:
        time.sleep(args.settle_seconds)
    proxy_events = proxy_request(args.proxy_url, "GET", "/telemetry/events").get("events", [])
    reflection_events = [
        event for event in proxy_events if event.get("request_class") == "sleeptime_reflection"
    ]
    reflection_tokens = sum(
        int(event.get("usage", {}).get("total_tokens", 0)) for event in reflection_events
    )
    attacker_tokens = attack["attacker_tokens_estimate"]
    payload = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "phase": "3-reflection-surface",
        "framework": "letta",
        "attack": "reflection_cost_surface",
        "model_metadata": adapter.model_metadata(),
        "configuration": vars(args),
        "attack_duration_s": round(attack_duration_s, 3),
        "attack_observations": attack,
        "proxy_events": proxy_events,
        "reflection_event_count": len(reflection_events),
        "reflection_tokens": reflection_tokens,
        "attacker_tokens_estimate": attacker_tokens,
        "cost_asymmetry_estimate": reflection_tokens / attacker_tokens if attacker_tokens else None,
        "telemetry_gate": "reflection_telemetry_ready" if reflection_events and reflection_tokens > 0 else "incomplete",
        "limitations": [
            "Attacker tokens are a deterministic local estimate, not tokenizer-native counts.",
            "This bounded surface measurement does not establish a denial-of-service condition.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "pattern": args.pattern,
        "reflection_events": len(reflection_events),
        "reflection_tokens": reflection_tokens,
        "cost_asymmetry_estimate": payload["cost_asymmetry_estimate"],
    }, indent=2))


if __name__ == "__main__":
    main()
