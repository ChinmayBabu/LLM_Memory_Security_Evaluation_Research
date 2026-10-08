"""Collect direct Letta log evidence and host resources when Docker permits it."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import psutil

from mabench.telemetry.direct import direct_telemetry_payload, parse_server_log_lines


def docker_resource_sample(containers: list[str]) -> dict[str, dict[str, object]]:
    """Collect one best-effort Docker stats sample, preserving failures."""
    try:
        result = subprocess.run(
            [
                "docker", "stats", "--no-stream", "--format",
                "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}",
                *containers,
            ],
            capture_output=True, text=True, check=True, timeout=30,
        )
    except Exception as exc:
        return {"collection_error": {"error": f"{type(exc).__name__}: {str(exc)[:300]}"}}
    samples: dict[str, dict[str, object]] = {}
    for line in result.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) != 4:
            continue
        samples[fields[0]] = {
            "cpu_percent": fields[1],
            "memory_usage": fields[2],
            "memory_percent": fields[3],
        }
    return samples


def host_process_resource_sample(name_fragment: str) -> dict[str, dict[str, object]]:
    """Sample matching host processes, such as a local Ollama process."""
    samples = {}
    for process in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            name = process.info.get("name") or ""
            if name_fragment.lower() not in name.lower():
                continue
            memory = process.info.get("memory_info")
            samples[str(process.info["pid"])] = {
                "name": name,
                "cpu_percent": process.info.get("cpu_percent"),
                "rss_bytes": memory.rss if memory else None,
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return samples


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--container", default="mabench-letta")
    parser.add_argument("--resource-container", action="append", default=[])
    parser.add_argument("--since", default="10m")
    parser.add_argument("--session-id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    error = None
    try:
        result = subprocess.run(["docker", "logs", "--timestamps", "--since", args.since, args.container], capture_output=True, text=True, check=True, timeout=30)
        events = parse_server_log_lines(result.stdout.splitlines() + result.stderr.splitlines(), session_id=args.session_id)
        direct = direct_telemetry_payload(events=events, available=True)
    except Exception as exc:
        direct = direct_telemetry_payload(events=[], available=False, error=f"{type(exc).__name__}: {str(exc)[:500]}")
    payload = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "phase": "direct-reflection-telemetry",
        "configuration": vars(args),
        "direct_server_telemetry": direct,
        "host_resource_sample": {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "rss_bytes": psutil.Process().memory_info().rss,
        },
        "docker_resource_sample": docker_resource_sample(
            list(dict.fromkeys([args.container, *args.resource_container]))
        ),
        "host_process_resource_sample": {
            "ollama": host_process_resource_sample("ollama"),
        },
        "proxy_telemetry_role": "fallback_only",
        "limitations": [
            "Log parsing is direct only when Docker logs contain explicit sleeptime markers and run identifiers.",
            "No direct token fields are inferred from timing or proxy events.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "direct_available": direct["available"], "events": len(direct["events"])}, indent=2))


if __name__ == "__main__":
    main()
