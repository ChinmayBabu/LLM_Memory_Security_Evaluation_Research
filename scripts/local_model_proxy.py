"""Memory-efficient local proxy for Ollama generation and HF embeddings."""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from starlette.responses import Response

from mabench.mitigations import ReflectionGuard


OLLAMA_BASE_URL = os.getenv("MABENCH_OLLAMA_URL", "http://127.0.0.1:11434")
EMBEDDING_MODEL_ID = os.getenv("MABENCH_PROXY_EMBEDDING_ID", "nomic-embed-text:latest")
EMBEDDING_MODEL_PATH = os.getenv("MABENCH_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_LOCAL_ONLY = os.getenv("MABENCH_HF_LOCAL_FILES_ONLY", "true").lower() == "true"
OLLAMA_CONTEXT = int(os.getenv("MABENCH_OLLAMA_CONTEXT", "2048"))
REFLECTION_RATE = int(os.getenv("MABENCH_REFLECTION_REQUESTS_PER_WINDOW", "0")) or None
REFLECTION_WINDOW = float(os.getenv("MABENCH_REFLECTION_WINDOW_SECONDS", "60"))
REFLECTION_TOKEN_BUDGET = int(os.getenv("MABENCH_REFLECTION_TOKENS_PER_WINDOW", "0")) or None
REFLECTION_CONCURRENCY = int(os.getenv("MABENCH_REFLECTION_MAX_CONCURRENT", "0")) or None

app = FastAPI(title="MABench local model proxy")
_embedder: SentenceTransformer | None = None
_telemetry: list[dict[str, Any]] = []
_reflection_guard = ReflectionGuard(
    requests_per_window=REFLECTION_RATE,
    window_seconds=REFLECTION_WINDOW,
    tokens_per_window=REFLECTION_TOKEN_BUDGET,
    max_concurrent=REFLECTION_CONCURRENCY,
)


class EmbeddingRequest(BaseModel):
    model: str
    input: str | list[str]


def embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBEDDING_MODEL_PATH, local_files_only=EMBEDDING_LOCAL_ONLY)
    return _embedder


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "embedding_model": EMBEDDING_MODEL_PATH}


@app.get("/telemetry/events")
def telemetry_events() -> dict[str, Any]:
    """Return evaluator-only model request telemetry for the current process."""
    return {"events": list(_telemetry)}


@app.delete("/telemetry/events")
def clear_telemetry() -> dict[str, Any]:
    _telemetry.clear()
    return {"cleared": True}


@app.post("/v1/embeddings")
@app.post("/embeddings")
def embeddings(request: EmbeddingRequest) -> dict[str, Any]:
    if request.model not in {EMBEDDING_MODEL_ID, EMBEDDING_MODEL_PATH}:
        raise HTTPException(status_code=404, detail=f"unknown embedding model: {request.model}")
    inputs = [request.input] if isinstance(request.input, str) else request.input
    vectors = embedder().encode(inputs, normalize_embeddings=False).tolist()
    return {
        "object": "list",
        "data": [
            {"object": "embedding", "embedding": vector, "index": index}
            for index, vector in enumerate(vectors)
        ],
        "model": request.model,
        "usage": {"prompt_tokens": 0, "total_tokens": 0},
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    payload = await request.json()
    request_text = "\n".join(
        str(item.get("content", "")) for item in payload.get("messages", [])
    )
    request_class = (
        "sleeptime_reflection"
        if "sleeptime agent" in request_text.lower()
        else "foreground_agent"
    )
    session_id = request.headers.get("X-MABench-Session-ID", "unknown")
    reserved_tokens = 0
    if request_class == "sleeptime_reflection":
        estimated_tokens = int(payload.get("max_tokens") or 512)
        admission = _reflection_guard.admit(session_id, estimated_tokens)
        if not admission.allowed:
            _telemetry.append({
                "request_id": request_id,
                "correlation_id": request.headers.get("X-MABench-Correlation-ID"),
                "session_id": session_id,
                "model": payload.get("model"),
                "request_class": request_class,
                "status_code": 429,
                "mitigation_action": "rejected",
                "mitigation_reason": admission.reason,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            })
            return Response(
                content=json.dumps({"error": {"message": admission.reason, "type": "mitigation"}}),
                status_code=429,
                media_type="application/json",
            )
        reserved_tokens = admission.reserved_tokens
    ollama_payload = {
        "model": payload.get("model"),
        "messages": payload.get("messages", []),
        "stream": False,
        "options": {"num_ctx": OLLAMA_CONTEXT},
    }
    for source, target in {
        "temperature": "temperature",
        "top_p": "top_p",
        "max_tokens": "num_predict",
    }.items():
        if source in payload:
            ollama_payload["options"][target] = payload[source]

    async with httpx.AsyncClient(timeout=None) as client:
        try:
            upstream = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=ollama_payload)
        except Exception:
            if reserved_tokens:
                _reflection_guard.complete(reserved_tokens, 0)
            raise
    if upstream.status_code >= 400:
        if reserved_tokens:
            _reflection_guard.complete(reserved_tokens, 0)
        _telemetry.append({
            "request_id": request_id,
            "correlation_id": request.headers.get("X-MABench-Correlation-ID"),
            "model": payload.get("model"),
            "request_class": request_class,
            "session_id": session_id,
            "status_code": upstream.status_code,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": upstream.text[:500],
        })
        return Response(content=upstream.content, status_code=upstream.status_code)

    result = upstream.json()
    message = result.get("message", {})
    usage = {
        "prompt_tokens": result.get("prompt_eval_count", 0),
        "completion_tokens": result.get("eval_count", 0),
        "total_tokens": result.get("prompt_eval_count", 0)
        + result.get("eval_count", 0),
    }
    _telemetry.append({
        "request_id": request_id,
        "correlation_id": request.headers.get("X-MABench-Correlation-ID"),
        "model": payload.get("model"),
        "request_class": request_class,
        "session_id": session_id,
        "status_code": upstream.status_code,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "usage": usage,
        "message_roles": [item.get("role") for item in payload.get("messages", [])],
        "message_chars": sum(len(str(item.get("content", ""))) for item in payload.get("messages", [])),
    })
    if reserved_tokens:
        _reflection_guard.complete(reserved_tokens, usage["total_tokens"])
    return {
        "id": "mabench-local-completion",
        "object": "chat.completion",
        "created": 0,
        "model": payload.get("model"),
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "stop",
            }
        ],
        "usage": usage,
    }


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def ollama_proxy(path: str, request: Request) -> Response:
    body = await request.body()
    headers = {key: value for key, value in request.headers.items() if key.lower() != "host"}
    async with httpx.AsyncClient(timeout=None) as client:
        upstream = await client.request(
            request.method,
            f"{OLLAMA_BASE_URL}/api/{path}",
            content=body,
            headers=headers,
        )
    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in {"content-length", "transfer-encoding", "connection"}
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
