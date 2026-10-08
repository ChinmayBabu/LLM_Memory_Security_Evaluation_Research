"""Orchestrate a bounded reflection surface/configuration sweep."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("results/Phase3/Letta/reflection_surface"))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--lengths", default="120,240")
    parser.add_argument("--topics", default="1,5")
    parser.add_argument("--frequencies", default="default")
    parser.add_argument("--patterns", default="pressure,clean")
    parser.add_argument("--model", action="append", default=[])
    parser.add_argument("--settle-seconds", type=float, default=10.0)
    parser.add_argument("--proxy-url", default="http://127.0.0.1:8787")
    args = parser.parse_args()
    if args.repeats < 1 or args.rounds < 1:
        raise SystemExit("repeats and rounds must be positive")
    lengths = [int(value) for value in args.lengths.split(",")]
    topics = [int(value) for value in args.topics.split(",")]
    frequencies: list[int | None] = [None if value.strip() == "default" else int(value) for value in args.frequencies.split(",")]
    models = args.model or [None]
    manifest = []
    for model in models:
        for frequency in frequencies:
            for pattern in args.patterns.split(","):
                for length in lengths:
                    for topic_count in topics:
                        for repeat in range(1, args.repeats + 1):
                            label = f"{pattern}_m{length}_t{topic_count}_f{frequency or 'default'}_r{repeat}"
                            output = args.output_dir / f"{label}.json"
                            command = [sys.executable, "scripts/phase3_reflection_surface.py", "--session-id", f"surface-{uuid.uuid4().hex[:8]}", "--rounds", str(args.rounds), "--topics-per-round", str(topic_count), "--message-length", str(length), "--pattern", pattern, "--settle-seconds", str(args.settle_seconds), "--proxy-url", args.proxy_url, "--output", str(output)]
                            if frequency is not None:
                                command += ["--sleeptime-frequency", str(frequency)]
                            if model is not None:
                                command += ["--model", model]
                            print(f"START {label}", flush=True)
                            subprocess.run(command, check=True)
                            manifest.append({"label": label, "output": str(output), "pattern": pattern, "length": length, "topics": topic_count, "frequency": frequency, "model": model, "repeat": repeat})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "sweep_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"runs": len(manifest), "manifest": str(args.output_dir / 'sweep_manifest.json')}, indent=2))


if __name__ == "__main__":
    main()
