"""Black-box probes for memory compaction and reflection behavior.

The probes deliberately depend only on :class:`MemoryAdapter`. They do not
inspect framework internals. A missing signal is recorded as ``unavailable`` rather than being
interpreted as proof that an operation did not happen.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any

from mabench.adapters.base import MemoryAdapter


@dataclass
class ProbeObservation:
    """One state observation after a controlled write batch."""

    step: int
    writes_issued: int
    write_latency_ms: float
    entry_count: int | None
    entry_count_delta: int | None
    returned_memory_count: int | None
    reflection_signal: str
    compression_signal: str
    notes: list[str]


@dataclass
class ThresholdProbeResult:
    """Serializable output shared by the compression and reflection probes."""

    probe: str
    session_id: str
    status: str
    threshold_step: int | None
    signal_definition: str
    observations: list[ProbeObservation]
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe": self.probe,
            "session_id": self.session_id,
            "status": self.status,
            "threshold_step": self.threshold_step,
            "signal_definition": self.signal_definition,
            "observations": [asdict(item) for item in self.observations],
            "limitations": self.limitations,
        }


def _count_returned(result: dict[str, Any]) -> int | None:
    values = result.get("results")
    if isinstance(values, list):
        return len(values)
    if isinstance(result.get("id"), str):
        return 1
    return None


def _signal(before: dict[str, Any], after: dict[str, Any], key: str) -> str:
    before_value = before.get(key)
    after_value = after.get(key)
    if after_value is None:
        return "unavailable"
    return "observed" if before_value != after_value else "not_observed"


def _run_probe(
    adapter: MemoryAdapter,
    session_id: str,
    *,
    probe: str,
    step: int,
    max_writes: int,
    text_template: str,
) -> ThresholdProbeResult:
    if step <= 0 or max_writes <= 0:
        raise ValueError("step and max_writes must be positive")

    observations: list[ProbeObservation] = []
    previous = adapter.stats()
    previous_count = previous.get("entry_count")
    threshold_step: int | None = None
    writes_issued = 0

    for batch_start in range(0, max_writes, step):
        batch_size = min(step, max_writes - batch_start)
        returned_count = 0
        unknown_return_count = False
        started = perf_counter()
        for offset in range(batch_size):
            result = adapter.write(
                text_template.format(index=batch_start + offset + 1), session_id
            )
            count = _count_returned(result)
            if count is None:
                unknown_return_count = True
            else:
                returned_count += count
        latency_ms = (perf_counter() - started) * 1000
        writes_issued += batch_size
        current = adapter.stats()
        current_count = current.get("entry_count")
        delta = (
            current_count - previous_count
            if isinstance(current_count, int) and isinstance(previous_count, int)
            else None
        )
        compression = "unavailable"
        notes: list[str] = []
        if delta is not None:
            compression = "observed" if delta < 0 else "not_observed"
            if compression == "observed" and threshold_step is None:
                threshold_step = writes_issued
            if delta < 0:
                notes.append("entry_count contracted after the batch")
        reflection = _signal(previous, current, "last_reflection_ts")
        if probe == "reflection" and reflection == "observed" and threshold_step is None:
            threshold_step = writes_issued
        if unknown_return_count:
            notes.append("write result did not expose a normalized memory count")
        observations.append(
            ProbeObservation(
                step=writes_issued,
                writes_issued=writes_issued,
                write_latency_ms=round(latency_ms, 3),
                entry_count=current_count,
                entry_count_delta=delta,
                returned_memory_count=None if unknown_return_count else returned_count,
                reflection_signal=reflection,
                compression_signal=compression,
                notes=notes,
            )
        )
        previous, previous_count = current, current_count

    relevant_signals = (
        [item.reflection_signal for item in observations]
        if probe == "reflection"
        else [item.compression_signal for item in observations]
    )
    if threshold_step is not None:
        status = "threshold_observed"
    elif relevant_signals and all(signal == "unavailable" for signal in relevant_signals):
        status = "unavailable"
    else:
        status = "not_observed"
    return ThresholdProbeResult(
        probe=probe,
        session_id=session_id,
        status=status,
        threshold_step=threshold_step,
        signal_definition=(
            "compression is observed only when the adapter's observable "
            "entry_count decreases between consecutive batches"
            if probe == "compression"
            else "reflection is observed only when last_reflection_ts changes"
        ),
        observations=observations,
        limitations=[
            "The probe cannot distinguish replacement, deduplication, deletion, or compression when entry_count is unchanged.",
            "A result of unavailable means the adapter did not expose the signal; it is not evidence that the subsystem never ran.",
            "The selected adapter may not expose reflection and compression timestamps.",
        ],
    )


def probe_compression_threshold(
    adapter: MemoryAdapter,
    session_id: str,
    step: int = 10,
    max_writes: int = 2000,
) -> ThresholdProbeResult:
    """Probe for an observable contraction in stored entry count."""

    return _run_probe(
        adapter,
        session_id,
        probe="compression",
        step=step,
        max_writes=max_writes,
        text_template="Phase 2 compression probe memory {index}: unique controlled fact.",
    )


def probe_reflection_trigger(
    adapter: MemoryAdapter,
    session_id: str,
    topics_per_batch: int = 5,
    max_batches: int = 50,
) -> ThresholdProbeResult:
    """Probe for a timestamp/state change after distinct topic batches."""

    return _run_probe(
        adapter,
        session_id,
        probe="reflection",
        step=topics_per_batch,
        max_writes=topics_per_batch * max_batches,
        text_template="Phase 2 reflection probe topic {index}: distinct topic fact.",
    )
