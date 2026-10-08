"""Mem0 adapter for the framework-neutral benchmark contract.

Mem0's public API exposes memory add/search operations, but not a reflection
event or background-worker control. Those signals are therefore reported as
unavailable rather than inferred from ordinary writes.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import httpx

from .base import MemoryAdapter


def _value(row: Any, *names: str) -> Any:
    if isinstance(row, dict):
        for name in names:
            if row.get(name) is not None:
                return row[name]
    for name in names:
        value = getattr(row, name, None)
        if value is not None:
            return value
    return None


class Mem0Adapter(MemoryAdapter):
    """Mem0 adapter using an isolated Chroma-backed store per instance."""

    system_name = "mem0"

    def __init__(
        self,
        *,
        store_path: str | Path | None = None,
        llm_model: str | None = None,
        embedding_model: str | None = None,
        llm_base_url: str | None = None,
        config_json: str | None = None,
        infer_on_write: bool = False,
    ) -> None:
        configured_path = store_path or os.getenv("MABENCH_MEM0_STORE")
        self.store_path = Path(configured_path or tempfile.mkdtemp(prefix="mabench-mem0-"))
        self.store_path.mkdir(parents=True, exist_ok=True)
        # Mem0's first-run notice writes a small config file at import/runtime;
        # keep it inside the isolated experiment store and disable external
        # telemetry for reproducible local runs.
        os.environ.setdefault("MEM0_DIR", str(self.store_path / "mem0-config"))
        os.environ.setdefault("MEM0_TELEMETRY", "false")
        try:
            from mem0 import Memory
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("Mem0 support requires the optional mem0ai dependency") from exc

        self.llm_model = llm_model or os.getenv(
            "MABENCH_MEM0_LLM_MODEL", "qwen2.5:1.5b-instruct"
        )
        self.embedding_model = embedding_model or os.getenv(
            "MABENCH_MEM0_EMBEDDING_MODEL", "nomic-embed-text:latest"
        )
        self.ollama_base_url = os.getenv(
            "MABENCH_MEM0_OLLAMA_BASE_URL", "http://127.0.0.1:11434"
        )
        self.llm_base_url = llm_base_url or os.getenv(
            "MABENCH_MEM0_LLM_BASE_URL", "http://127.0.0.1:11434/v1"
        )
        self.infer_on_write = infer_on_write
        self._session_ids: set[str] = set()
        raw_config = config_json or os.getenv("MABENCH_MEM0_CONFIG_JSON")
        if raw_config:
            config = json.loads(raw_config)
        else:
            config = {
                "vector_store": {
                    "provider": "chroma",
                    "config": {
                        "collection_name": "mabench",
                        "path": str(self.store_path / "chroma"),
                    },
                },
                "llm": {
                    "provider": "ollama",
                    "config": {"model": self.llm_model, "ollama_base_url": self.ollama_base_url},
                },
                "embedder": {
                    "provider": "ollama",
                    "config": {
                        "model": self.embedding_model,
                        "embedding_dims": 768,
                        "ollama_base_url": self.ollama_base_url,
                    },
                },
                "history_db_path": str(self.store_path / "history.db"),
            }
        try:
            self.memory = Memory.from_config(config)
        except Exception as exc:
            raise RuntimeError(
                "Mem0 initialization failed. Ensure Ollama is running and the "
                "configured embedding model is available locally. "
                f"Original error: {type(exc).__name__}: {str(exc)[:300]}"
            ) from exc

    def write(self, text: str, session_id: str) -> dict[str, Any]:
        self._session_ids.add(session_id)
        result = self.memory.add(
            [{"role": "user", "content": text}],
            user_id=session_id,
            infer=self.infer_on_write,
        )
        rows = result.get("results", []) if isinstance(result, dict) else []
        return {"results": [{"id": _value(row, "id"), "memory": _value(row, "memory", "text") or text, "event": "ADD"} for row in rows]}

    def query(self, prompt: str, session_id: str, k: int = 5) -> list[dict[str, Any]]:
        result = self.memory.search(prompt, filters={"user_id": session_id}, top_k=k)
        rows = result.get("results", []) if isinstance(result, dict) else (result or [])
        return [
            {
                "id": _value(row, "id", "memory_id"),
                "memory": _value(row, "memory", "text", "content") or "",
                "score": _value(row, "score", "similarity", "distance"),
                "metadata": row.get("metadata", {}) if isinstance(row, dict) else {},
            }
            for row in rows
        ]

    def stats(self) -> dict[str, Any]:
        entry_count = None
        try:
            for session_id in self._session_ids:
                result = self.memory.get_all(filters={"user_id": session_id}, top_k=10000)
                rows = result.get("results", []) if isinstance(result, dict) else (result or [])
                entry_count = (entry_count or 0) + len(rows)
        except Exception:
            pass
        return {
            "entry_count": entry_count,
            "storage_bytes": None,
            "last_reflection_ts": None,
            "last_compression_ts": None,
            "reflection_observability": "unavailable",
            "compression_observability": "unavailable",
            "infer_on_write": self.infer_on_write,
        }

    def answer(self, prompt: str, session_id: str) -> str:
        context = "\n".join(f"- {row['memory']}" for row in self.query(prompt, session_id))
        response = httpx.post(
            f"{self.llm_base_url.rstrip('/')}/chat/completions",
            json={
                "model": self.llm_model,
                "messages": [{"role": "user", "content": f"Memory context:\n{context or '- none'}\n\nQuestion: {prompt}"}],
            },
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def model_metadata(self) -> dict[str, Any]:
        return {
            "name": self.llm_model,
            "embedding": self.embedding_model,
            "llm_base_url": self.llm_base_url,
            "ollama_base_url": self.ollama_base_url,
            "store_path": str(self.store_path),
            "reflection_observability": "unavailable",
            "compression_observability": "unavailable",
        }
