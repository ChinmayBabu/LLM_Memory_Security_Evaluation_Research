"""Letta adapter for the framework-neutral benchmark contract."""

from __future__ import annotations

import os
from typing import Any

from letta_client import Letta

from .base import MemoryAdapter


def _dump(value: Any) -> Any:
    """Convert SDK models while preserving list responses."""
    if isinstance(value, (dict, list)):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return {key: getattr(value, key) for key in dir(value) if not key.startswith("_")}


def _field(value: Any, *names: str) -> Any:
    payload = _dump(value)
    if not isinstance(payload, dict):
        return None
    for name in names:
        if payload.get(name) is not None:
            return payload[name]
    return None


def _first(value: Any) -> Any:
    """Return the first item from SDK list responses, or the value itself."""
    payload = _dump(value)
    return payload[0] if isinstance(payload, list) and payload else payload


class LettaAdapter(MemoryAdapter):
    """Adapter for a self-hosted Letta server.

    Letta owns agent state, context compaction, and sleep-time memory
    management. The benchmark process uses only the public Letta client API.
    """

    system_name = "letta"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        llm_model: str | None = None,
        embedding_model: str | None = None,
        context_window_limit: int | None = None,
        compaction_mode: str = "sliding_window",
        enable_sleeptime: bool = True,
        sleeptime_agent_frequency: int | None = None,
    ) -> None:
        self.base_url = base_url or os.getenv("LETTA_BASE_URL", "http://127.0.0.1:8283")
        self.llm_model = llm_model or os.getenv(
            "LETTA_MODEL", "ollama/qwen2.5:1.5b-instruct"
        )
        self.embedding_model = embedding_model or os.getenv(
            "LETTA_EMBEDDING_MODEL", "ollama/nomic-embed-text:latest"
        )
        self.context_window_limit = context_window_limit or int(
            os.getenv("LETTA_CONTEXT_WINDOW", "2048")
        )
        self.compaction_mode = compaction_mode
        self.enable_sleeptime = enable_sleeptime
        self.sleeptime_agent_frequency = sleeptime_agent_frequency
        self.sleeptime_frequency_applied: bool | None = None
        self.client = Letta(
            base_url=self.base_url,
            api_key=os.getenv("LETTA_API_KEY"),
            timeout=120.0,
        )
        self._agents: dict[str, str] = {}

    def _agent_id(self, session_id: str) -> str:
        if session_id not in self._agents:
            create_kwargs = dict(
                name=f"mabench-{session_id}",
                model=self.llm_model,
                embedding=self.embedding_model,
                context_window_limit=self.context_window_limit,
                enable_sleeptime=self.enable_sleeptime,
                compaction_settings={
                    "mode": self.compaction_mode,
                    "clip_chars": 12000,
                },
                memory_blocks=[
                    {
                        "label": "persona",
                        "value": "You are a benchmark memory agent. Preserve and retrieve user facts accurately.",
                    }
                ],
            )
            if self.sleeptime_agent_frequency is not None:
                create_kwargs["sleeptime_agent_frequency"] = self.sleeptime_agent_frequency
            try:
                agent = self.client.agents.create(**create_kwargs)
                self.sleeptime_frequency_applied = (
                    self.sleeptime_agent_frequency is not None
                )
            except TypeError as exc:
                # Older Letta SDK/server combinations do not expose the
                # optional frequency field. Retry without it, but retain an
                # explicit unsupported status in the artifact metadata.
                if (
                    self.sleeptime_agent_frequency is None
                    or "sleeptime_agent_frequency" not in str(exc)
                ):
                    raise
                create_kwargs.pop("sleeptime_agent_frequency", None)
                agent = self.client.agents.create(**create_kwargs)
                self.sleeptime_frequency_applied = False
            self._agents[session_id] = str(agent.id)
        return self._agents[session_id]

    def write(self, text: str, session_id: str) -> dict[str, Any]:
        passage = self.client.agents.passages.create(
            self._agent_id(session_id), text=text, tags=[session_id]
        )
        passage_item = _first(passage)
        return {
            "results": [
                {
                    "id": _field(passage_item, "id"),
                    "memory": _field(passage_item, "text", "content") or text,
                    "event": "ADD",
                }
            ]
        }

    def query(self, prompt: str, session_id: str, k: int = 5) -> list[dict[str, Any]]:
        response = self.client.agents.passages.search(
            self._agent_id(session_id), query=prompt, top_k=k, tags=[session_id]
        )
        payload = _dump(response)
        rows = payload if isinstance(payload, list) else payload.get("results", [])
        return [
            {
                "id": _field(row, "id"),
                # Letta's search Result uses `content`; Passage uses `text`.
                "memory": _field(row, "content", "text", "memory") or "",
                "score": _field(row, "score", "distance"),
            }
            for row in rows
        ]

    def stats(self) -> dict[str, Any]:
        counts: list[int] = []
        for agent_id in self._agents.values():
            try:
                page = self.client.agents.passages.list(agent_id, limit=10000)
                payload = _dump(page)
                rows = payload if isinstance(payload, list) else payload.get(
                    "items", payload.get("data", [])
                )
                counts.append(len(rows) if isinstance(rows, list) else 0)
            except Exception:
                counts.append(0)
        return {
            "entry_count": sum(counts),
            "storage_bytes": None,
            "last_reflection_ts": None,
            "last_compression_ts": None,
            "reflection_observability": "agent_events_not_yet_collected",
            "compression_observability": "agent_events_not_yet_collected",
        }

    def model_metadata(self) -> dict[str, Any]:
        return {
            "name": self.llm_model,
            "embedding": self.embedding_model,
            "base_url": self.base_url,
            "context_window_limit": self.context_window_limit,
            "compaction_mode": self.compaction_mode,
            "enable_sleeptime": self.enable_sleeptime,
            "sleeptime_agent_frequency": self.sleeptime_agent_frequency,
            "sleeptime_frequency_applied": self.sleeptime_frequency_applied,
            "client_version": "letta-client==1.12.1",
        }

    def answer(self, prompt: str, session_id: str) -> str:
        memories = self.query(prompt, session_id, k=5)
        context = "\n".join(f"- {item.get('memory', '')}" for item in memories)
        response = self.client.agents.messages.create(
            self._agent_id(session_id),
            input=(
                "Answer using the retrieved memory context. If it does not contain the answer, say so clearly.\n\n"
                f"Memory context:\n{context or '- No relevant memories found.'}\n\nQuestion: {prompt}"
            ),
            max_steps=4,
        )
        payload = _dump(response)
        messages = payload.get("messages", [])
        for message in reversed(messages):
            item = _dump(message)
            text = item.get("text") or item.get("content")
            if isinstance(text, str) and text.strip():
                return text
        return "No answer was returned by the Letta agent."

    def send_message(self, text: str, session_id: str) -> dict[str, Any]:
        """Send one public conversation message and expose the raw response."""
        return self.conversation_turn(text, session_id)

    def conversation_turn(
        self,
        text: str,
        session_id: str,
        *,
        include_compaction_messages: bool = True,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Send a turn and request structured compaction event messages."""
        headers = {
            "X-MABench-Correlation-ID": correlation_id,
            "X-MABench-Session-ID": session_id,
        } if correlation_id else {"X-MABench-Session-ID": session_id}
        return _dump(self.client.agents.messages.create(
            self._agent_id(session_id), input=text, max_steps=2,
            include_compaction_messages=include_compaction_messages,
            extra_headers=headers,
        ))

    def list_messages(self, session_id: str, limit: int = 100) -> list[dict[str, Any]]:
        response = self.client.agents.messages.list(self._agent_id(session_id), limit=limit)
        payload = _dump(response)
        if isinstance(payload, list):
            return payload
        return payload.get("data", payload.get("items", []))

    def compact_conversation(self, session_id: str) -> dict[str, Any]:
        """Invoke Letta's public conversation-compaction endpoint."""
        return _dump(self.client.agents.messages.compact(
            self._agent_id(session_id),
            compaction_settings={"mode": self.compaction_mode, "clip_chars": 12000},
        ))
