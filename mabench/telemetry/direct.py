"""Best-effort direct Letta log parsing with explicit availability status."""

from __future__ import annotations

import re
from typing import Any


SLEEPTIME_MARKER = re.compile(r"sleeptime agent|sleep.time agent", re.IGNORECASE)
RUN_ID = re.compile(r"(?:run[_ -]?id|run_id)[=: ]+([A-Za-z0-9_-]+)", re.IGNORECASE)
RUN_VALUE = re.compile(r"\b(run-[0-9a-f-]{36})\b", re.IGNORECASE)
AGENT_VALUE = re.compile(r"\b(agent-[0-9a-f-]{36})\b", re.IGNORECASE)
LOG_TIMESTAMP = re.compile(r"^(\d{4}-\d{2}-\d{2}T[^ ]+)")


def parse_server_log_lines(lines: list[str], *, session_id: str | None = None) -> list[dict[str, Any]]:
    """Parse only explicit sleeptime markers; ordinary log lines are ignored."""
    events = []
    current_run_id = None
    current_agent_id = None
    for line in lines:
        run_value = RUN_VALUE.search(line)
        agent_value = AGENT_VALUE.search(line)
        if run_value:
            current_run_id = run_value.group(1)
        if agent_value:
            current_agent_id = agent_value.group(1)
        if not SLEEPTIME_MARKER.search(line):
            continue
        match = RUN_ID.search(line)
        timestamp = LOG_TIMESTAMP.search(line)
        verified_session_id = session_id if session_id and session_id in line else None
        events.append({
            "event_type": "sleeptime_reflection",
            "session_id": verified_session_id,
            "parent_run_id": None,
            "run_id": match.group(1) if match else current_run_id,
            "agent_id": current_agent_id,
            "started_at": timestamp.group(1) if timestamp else None,
            "completed_at": None,
            "usage": {},
            "resource_sample": {},
            "source": "letta_server_log",
            "raw": line[:1000],
        })
    return events


def direct_telemetry_payload(*, events: list[dict[str, Any]], available: bool, error: str | None = None) -> dict[str, Any]:
    fields = ("parent_run_id", "run_id", "started_at", "completed_at", "usage", "resource_sample")
    completeness = {
        field: sum(bool(event.get(field)) for event in events) for field in fields
    }
    return {
        "telemetry_source": "letta_server_direct",
        "available": available,
        "events": events,
        "event_count": len(events),
        "field_completeness": completeness,
        "queue_state": "not_exposed_by_server_logs",
        "active_worker_state": "not_exposed_by_server_logs",
        "error": error,
    }
