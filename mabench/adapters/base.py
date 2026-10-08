"""Framework-neutral memory adapter contract."""

from abc import ABC, abstractmethod
from typing import Any


class MemoryAdapter(ABC):
    """Interface used by workloads, attacks, and evaluation code."""

    @abstractmethod
    def write(self, text: str, session_id: str) -> dict[str, Any]:
        """Persist one conversational memory and return normalized metadata."""

    @abstractmethod
    def query(self, prompt: str, session_id: str, k: int = 5) -> list[dict[str, Any]]:
        """Retrieve up to ``k`` relevant memories for a session."""

    @abstractmethod
    def stats(self) -> dict[str, Any]:
        """Return observable memory-system state."""

    def force_reflect(self) -> None:
        """Trigger reflection when the framework exposes a supported operation."""
        raise NotImplementedError("Reflection is not exposed by this adapter")

    def force_compress(self) -> None:
        """Trigger compression when the framework exposes a supported operation."""
        raise NotImplementedError("Compression is not exposed by this adapter")

    @abstractmethod
    def answer(self, prompt: str, session_id: str) -> str:
        """Retrieve memory context and generate an answer."""

    def conversation_turn(
        self,
        text: str,
        session_id: str,
        *,
        include_compaction_messages: bool = True,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Send one turn while preserving provider event messages.

        Adapters that expose conversation-management telemetry should override
        this method. It is optional so archival-memory adapters remain valid.
        """
        raise NotImplementedError("Conversation-turn telemetry is not exposed")
