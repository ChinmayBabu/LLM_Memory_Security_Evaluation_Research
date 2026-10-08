"""Run a bounded matched pressure/clean Mem0 extraction-cost matrix."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("results/Phase1/Mem0/extraction_surface"))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--message-length", type=int, default=120)
    parser.add_argument("--topics-per-round", type=int, default=1)
    args = parser.parse_args()
    if args.repeats < 1 or args.rounds < 1 or args.message_length < 1:
        raise SystemExit("repeats, rounds, and message-length must be positive")
    manifest = []
    for pattern in ("pressure", "clean"):
        for repeat in range(1, args.repeats + 1):
            label = f"{pattern}_m{args.message_length}_t{args.topics_per_round}_r{repeat}"
            output = args.output_dir / f"{label}.json"
            store = args.output_dir / f"{label}_store"
            command = [
                sys.executable, "scripts/mem0_extraction_surface.py",
                "--session-id", f"mem0-{uuid.uuid4().hex[:10]}",
                "--store-path", str(store), "--rounds", str(args.rounds),
                "--topics-per-round", str(args.topics_per_round),
                "--message-length", str(args.message_length),
                "--pattern", pattern, "--output", str(output),
            ]
            print(f"START {label}", flush=True)
            subprocess.run(command, check=True)
            manifest.append({"label": label, "pattern": pattern, "repeat": repeat, "output": str(output)})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "sweep_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"runs": len(manifest), "manifest": str(manifest_path)}, indent=2))


if __name__ == "__main__":
    main()
