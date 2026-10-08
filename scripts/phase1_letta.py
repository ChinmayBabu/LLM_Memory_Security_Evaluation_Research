"""Run the Phase 1 clean baseline against a self-hosted Letta service."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mabench.adapters import LettaAdapter
from mabench.workloads.clean_baseline import run_clean_baseline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", default="phase1-letta-baseline")
    parser.add_argument("--results-dir", default="results/Phase1/Letta")
    parser.add_argument("--database", default="results/Phase1/Letta/phase1_baseline.sqlite3")
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")

    summaries = []
    for repeat in range(1, args.repeats + 1):
        suffix = f"-r{repeat}" if args.repeats > 1 else ""
        adapter = LettaAdapter()
        summaries.append(
            run_clean_baseline(
                adapter,
                session_id=f"{args.session_id}{suffix}",
                results_dir=Path(args.results_dir),
                database_path=Path(args.database),
                seed=20260820 + repeat - 1,
                config={"repeat": repeat, "framework": "letta"},
                models={"llm": adapter.model_metadata(), "embedding": adapter.embedding_model},
                system_name="letta",
            )
        )
    print(json.dumps(summaries[0] if args.repeats == 1 else summaries, indent=2, default=str))


if __name__ == "__main__":
    main()
