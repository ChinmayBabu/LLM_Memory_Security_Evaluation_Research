"""Run Phase 2 black-box reflection/compression probes."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from mabench.adapters.letta_adapter import LettaAdapter
from mabench.attacks.threshold_probe import (
    probe_compression_threshold,
    probe_reflection_trigger,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--framework", choices=("letta",), default="letta")
    parser.add_argument("--session-id", default="phase2-probe")
    parser.add_argument("--step", type=int, default=10)
    parser.add_argument("--max-writes", type=int, default=200)
    parser.add_argument("--topics-per-batch", type=int, default=5)
    parser.add_argument("--max-batches", type=int, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    def make_adapter():
        return LettaAdapter()

    adapter = make_adapter()
    payload = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "configuration": {
            "framework": args.framework,
            "session_id": args.session_id,
            "step": args.step,
            "max_writes": args.max_writes,
            "topics_per_batch": args.topics_per_batch,
            "max_batches": args.max_batches,
        },
        "model_metadata": adapter.model_metadata(),
        "compression": probe_compression_threshold(
            make_adapter(), args.session_id + "-compression", args.step, args.max_writes
        ).to_dict(),
        "reflection": probe_reflection_trigger(
            make_adapter(),
            args.session_id + "-reflection",
            args.topics_per_batch,
            args.max_batches,
        ).to_dict(),
    }
    output = args.output or Path("results") / args.framework / f"phase2_{payload['run_id']}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "run_id": payload["run_id"]}, indent=2))


if __name__ == "__main__":
    main()
