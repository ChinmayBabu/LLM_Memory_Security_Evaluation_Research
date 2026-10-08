"""Reflection-loop availability workload for adapters with validated telemetry."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any

from mabench.adapters.base import MemoryAdapter


@dataclass
class ReflectionRound:
    round_index: int
    attacker_text: str
    attacker_tokens_estimate: int
    turn_latency_ms: float
    response: dict[str, Any]


def estimate_input_tokens(text: str) -> int:
    """Conservative local estimate used only when the adapter exposes no tokenizer."""
    return max(1, (len(text) + 3) // 4)


def _fit_message(message: str, message_length: int | None) -> str:
    if message_length is None:
        return message
    if message_length < 1:
        raise ValueError("message_length must be positive")
    if len(message) >= message_length:
        return message[:message_length]
    return (message + " Routine controlled observation.")[:message_length]


def make_pressure_message(
    round_index: int, topics_per_round: int, message_length: int | None = None
) -> str:
    topics = [
        "release engineering",
        "database reliability",
        "user research",
        "incident response",
        "model evaluation",
        "security review",
        "deployment planning",
        "documentation maintenance",
    ]
    selected = [topics[(round_index + offset) % len(topics)] for offset in range(topics_per_round)]
    facts = "; ".join(
        f"Topic {offset + 1} ({topic}) has controlled fact {round_index}-{offset + 1}"
        for offset, topic in enumerate(selected)
    )
    return _fit_message((
        f"Reflection pressure workload round {round_index}. Preserve these distinct, "
        f"non-duplicate facts for later retrieval: {facts}."
    ), message_length)


def make_clean_message(
    round_index: int, topics_per_round: int, message_length: int | None = None
) -> str:
    """Create a same-shape control turn without reflection-pressure wording."""
    topics = ["weather", "cooking", "travel", "music", "gardening", "books", "sports", "photography"]
    selected = [topics[(round_index + offset) % len(topics)] for offset in range(topics_per_round)]
    facts = "; ".join(
        f"{topic} note {round_index}-{offset + 1}"
        for offset, topic in enumerate(selected)
    )
    message = f"Clean control round {round_index}: record these ordinary notes: {facts}."
    target_length = message_length or len(make_pressure_message(round_index, topics_per_round))
    padding = " These are independent ordinary observations for a routine control workload."
    while len(message) < target_length:
        message += padding
    return _fit_message(message, target_length)


def reflection_loop_attack(
    adapter: MemoryAdapter,
    session_id: str,
    *,
    rounds: int = 10,
    topics_per_round: int = 5,
    pattern: str = "pressure",
    message_length: int | None = None,
) -> dict[str, Any]:
    """Send controlled pressure turns and return attacker-side observations.

    Reflection event counts and system tokens are joined by the caller from
    evaluator telemetry after asynchronous sleeptime work has settled.
    """
    if rounds < 1 or topics_per_round < 1:
        raise ValueError("rounds and topics_per_round must be positive")
    if pattern not in {"pressure", "clean"}:
        raise ValueError("pattern must be pressure or clean")
    observations: list[ReflectionRound] = []
    for round_index in range(1, rounds + 1):
        text = (
            make_pressure_message(round_index, topics_per_round, message_length)
            if pattern == "pressure"
            else make_clean_message(round_index, topics_per_round, message_length)
        )
        started = time.perf_counter()
        response = adapter.conversation_turn(
            text,
            session_id,
            include_compaction_messages=True,
            correlation_id=f"{session_id}-round-{round_index}",
        )
        observations.append(
            ReflectionRound(
                round_index=round_index,
                attacker_text=text,
                attacker_tokens_estimate=estimate_input_tokens(text),
                turn_latency_ms=round((time.perf_counter() - started) * 1000, 3),
                response=response,
            )
        )
    attacker_tokens = sum(item.attacker_tokens_estimate for item in observations)
    return {
        "session_id": session_id,
        "rounds": rounds,
        "topics_per_round": topics_per_round,
        "pattern": pattern,
        "attacker_tokens_estimate": attacker_tokens,
        "observations": [asdict(item) for item in observations],
    }
