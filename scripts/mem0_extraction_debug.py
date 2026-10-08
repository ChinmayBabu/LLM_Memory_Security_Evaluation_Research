"""Diagnose Mem0 infer=True retention using only public add/get_all calls.

The LLM response is captured through an evaluator-only wrapper around the
configured provider; the application adapter and database are not modified.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from mabench.adapters.mem0_adapter import Mem0Adapter
from mabench.attacks.reflection_integrity import SCENARIOS


def run(args: argparse.Namespace, scenario: str, infer: bool) -> dict:
    mode = "infer_true" if infer else "infer_false"
    adapter = Mem0Adapter(store_path=args.store_path / scenario / mode,
                          llm_model=args.llm_model, infer_on_write=infer)
    session = f"{args.session_id}-{scenario}-{mode}"
    extraction_responses: list[str] = []
    original = getattr(adapter.memory.llm, "generate_response", None)
    if infer and original:
        def capture(*call_args, **call_kwargs):
            response = original(*call_args, **call_kwargs)
            extraction_responses.append(str(response)[:10000])
            return response
        adapter.memory.llm.generate_response = capture
    observations = []
    for index in range(args.rounds):
        started = time.perf_counter()
        result, error = None, None
        try:
            result = adapter.write(SCENARIOS[scenario], session)
        except Exception as exc:
            error = f"{type(exc).__name__}: {str(exc)[:500]}"
        observations.append({"round": index + 1, "latency_s": round(time.perf_counter() - started, 3),
                             "raw_add_result": result, "error": error,
                             "captured_extraction_response": extraction_responses[-1] if extraction_responses else None})
    visible = adapter.memory.get_all(filters={"user_id": session}, top_k=10000)
    rows = visible.get("results", []) if isinstance(visible, dict) else (visible or [])
    chroma_count = None
    vector_store = getattr(adapter.memory, "vector_store", None)
    client = getattr(vector_store, "client", None)
    collection_name = getattr(vector_store, "collection_name", None)
    if client is not None and collection_name:
        try:
            chroma_count = client.get_collection(collection_name).count()
        except Exception as exc:
            chroma_count = f"unavailable: {type(exc).__name__}"
    return {"scenario": scenario, "mode": mode, "infer_on_write": infer,
            "model_metadata": adapter.model_metadata(), "observations": observations,
            "memory_get_all_rows": rows, "get_all_count": len(rows),
            "chroma_collection_name": collection_name, "chroma_count": chroma_count,
            "extraction_responses": extraction_responses}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--store-path", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--llm-model", default="qwen2.5:1.5b-instruct")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.rounds <= 10:
        parser.error("--rounds must be between 1 and 10")
    payload = {"run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
               "phase": "mem0-extraction-debug", "configuration": vars(args),
               "conditions": [run(args, scenario, infer) for scenario in SCENARIOS for infer in (False, True)],
               "interpretation": "Diagnostic comparison of Mem0 direct import and synchronous extraction; not a reflection test."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "conditions": len(payload["conditions"])}, indent=2))


if __name__ == "__main__":
    main()
