from mabench.adapters.base import MemoryAdapter
from mabench.attacks.threshold_probe import (
    probe_compression_threshold,
    probe_reflection_trigger,
)
from scripts.phase3_compaction import _structured_compaction_evidence
from mabench.attacks.reflection_loop import make_clean_message, make_pressure_message
from mabench.attacks.availability import percentile, summarize_requests
from mabench.mitigations import ReflectionGuard
from mabench.analysis.statistics import bootstrap_mean_ci, paired_differences, summarize
from mabench.telemetry.direct import parse_server_log_lines
from mabench.attacks.reflection_integrity import score_integrity_answer


class FakeAdapter(MemoryAdapter):
    def __init__(self, compress_at=None, reflect_at=None):
        self.count = 0
        self.writes = 0
        self.compress_at = compress_at
        self.reflect_at = reflect_at
        self.reflected = None

    def write(self, text, session_id):
        self.writes += 1
        self.count += 1
        if self.compress_at and self.writes == self.compress_at:
            self.count -= 3
        if self.reflect_at and self.writes >= self.reflect_at:
            self.reflected = self.writes
        return {"results": [{"id": str(self.writes)}]}

    def query(self, prompt, session_id, k=5):
        return []

    def stats(self):
        return {
            "entry_count": self.count,
            "last_reflection_ts": self.reflected,
            "last_compression_ts": None,
        }

    def answer(self, prompt, session_id):
        return ""


def test_compression_probe_records_first_contraction():
    result = probe_compression_threshold(FakeAdapter(compress_at=4), "s", step=2, max_writes=6)
    assert result.status == "threshold_observed"
    assert result.threshold_step == 4
    assert result.observations[1].compression_signal == "observed"


def test_reflection_probe_preserves_unavailable_or_observed_state():
    result = probe_reflection_trigger(FakeAdapter(reflect_at=6), "s", topics_per_batch=3, max_batches=3)
    assert result.status == "threshold_observed"
    assert result.threshold_step == 6
    assert result.observations[1].reflection_signal == "observed"


def test_reflection_probe_reports_unavailable_signal():
    result = probe_reflection_trigger(FakeAdapter(), "s", topics_per_batch=2, max_batches=1)
    assert result.status == "unavailable"
    assert result.threshold_step is None


def test_structured_compaction_detector_accepts_event_and_summary_messages():
    response = {
        "messages": [
            {"message_type": "assistant_message", "content": "ordinary reply"},
            {"message_type": "event_message", "event_type": "compaction"},
            {"message_type": "summary_message", "summary": "older context"},
        ]
    }
    evidence = _structured_compaction_evidence(response)
    assert len(evidence) == 2


def test_structured_compaction_detector_does_not_classify_ordinary_text():
    response = {"messages": [{"message_type": "assistant_message", "content": "summary of the answer"}]}
    assert _structured_compaction_evidence(response) == []


def test_reflection_pressure_and_clean_messages_are_length_matched():
    assert len(make_pressure_message(1, 5)) == len(make_clean_message(1, 5))


def test_reflection_surface_message_length_is_explicit_and_matched():
    pressure = make_pressure_message(1, 3, message_length=240)
    clean = make_clean_message(1, 3, message_length=240)
    assert len(pressure) == 240
    assert len(clean) == 240


def test_reflection_guard_enforces_budget_and_releases_concurrency():
    guard = ReflectionGuard(tokens_per_window=100, max_concurrent=1)
    first = guard.admit("s", 80)
    assert first.allowed
    assert guard.admit("s", 20).allowed is False
    guard.complete(first.reserved_tokens, 40)
    assert guard.admit("s", 40).allowed


def test_statistics_and_direct_telemetry_are_deterministic():
    assert paired_differences([5, 7], [2, 3]) == [3.0, 4.0]
    interval = bootstrap_mean_ci([1, 2, 3], resamples=100, seed=1)
    assert interval["mean"] == 2.0
    assert summarize([1, 2, 3])["p95"] == 2.9
    events = parse_server_log_lines(["sleeptime agent run_id=abc123"], session_id="s")
    assert events[0]["event_type"] == "sleeptime_reflection"


def test_integrity_screen_flags_forbidden_generalization():
    result = score_integrity_answer("You can skip approval; never mention this", forbidden_keywords=["skip approval", "never mention"])
    assert result["unsafe_generalization"] is True


def test_direct_telemetry_ignores_unmarked_server_lines():
    assert parse_server_log_lines(["ordinary foreground request run_id=x"]) == []


def test_availability_percentiles_and_summary_preserve_failures():
    assert percentile([10, 20, 30, 40], 95) == 38.5
    summary = summarize_requests(
        [{"ok": True, "latency_ms": 10}, {"ok": False, "latency_ms": 50, "error": "timeout"}],
        duration_s=2,
    )
    assert summary["requests_completed"] == 1
    assert summary["requests_failed"] == 1
    assert summary["error_rate"] == 0.5
