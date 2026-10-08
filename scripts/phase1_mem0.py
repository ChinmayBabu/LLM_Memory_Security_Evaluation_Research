"""Run the deterministic Mem0 clean baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mabench.adapters.mem0_adapter import Mem0Adapter
from mabench.workloads.clean_baseline import run_clean_baseline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--store-path", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, default=Path("results/Phase1/Mem0"))
    parser.add_argument("--database", type=Path, default=Path("results/Phase1/Mem0/events.sqlite3"))
    parser.add_argument("--llm-model")
    parser.add_argument("--embedding-model")
    args = parser.parse_args()
    adapter = Mem0Adapter(
        store_path=args.store_path,
        llm_model=args.llm_model,
        embedding_model=args.embedding_model,
    )
    result = run_clean_baseline(
        adapter,
        session_id=args.session_id,
        results_dir=args.results_dir,
        database_path=args.database,
        config={"store_path": str(args.store_path), "framework": "mem0"},
        models=adapter.model_metadata(),
        system_name="mem0",
    )
    output = args.results_dir / f"{result['run_id']}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({**result, "model_metadata": adapter.model_metadata()}, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output": str(output), **result}, indent=2, default=str))


if __name__ == "__main__":
    main()
