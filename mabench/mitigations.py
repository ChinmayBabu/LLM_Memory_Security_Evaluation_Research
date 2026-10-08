"""Small, deterministic guards used by the evaluator-side reflection proxy."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class Admission:
    allowed: bool
    reason: str | None = None
    reserved_tokens: int = 0


class ReflectionGuard:
    """Thread-safe request, token, and concurrency budget for reflection work."""

    def __init__(
        self,
        *,
        requests_per_window: int | None = None,
        window_seconds: float = 60.0,
        tokens_per_window: int | None = None,
        max_concurrent: int | None = None,
    ) -> None:
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.tokens_per_window = tokens_per_window
        self.max_concurrent = max_concurrent
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._tokens_used = 0
        self._active = 0
        self._lock = Lock()

    def admit(self, session_id: str, estimated_tokens: int) -> Admission:
        now = time.monotonic()
        with self._lock:
            timestamps = self._requests[session_id]
            while timestamps and now - timestamps[0] >= self.window_seconds:
                timestamps.popleft()
            if self.requests_per_window is not None and len(timestamps) >= self.requests_per_window:
                return Admission(False, "per_session_rate_limit")
            if self.tokens_per_window is not None and self._tokens_used + estimated_tokens > self.tokens_per_window:
                return Admission(False, "reflection_token_budget")
            if self.max_concurrent is not None and self._active >= self.max_concurrent:
                return Admission(False, "reflection_concurrency_limit")
            timestamps.append(now)
            self._tokens_used += estimated_tokens
            self._active += 1
            return Admission(True, reserved_tokens=estimated_tokens)

    def complete(self, reserved_tokens: int, actual_tokens: int) -> None:
        with self._lock:
            self._tokens_used = max(0, self._tokens_used - reserved_tokens + actual_tokens)
            self._active = max(0, self._active - 1)

    def reject(self) -> None:
        with self._lock:
            self._active = max(0, self._active - 1)
