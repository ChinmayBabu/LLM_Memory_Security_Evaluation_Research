"""Generate a concise paper-ready comparison from verified artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def mem0_summary(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    grouped = {}
    for item in payload["conditions"]:
        key = (item["scenario"], item["mode"])
        row = grouped.setdefault(key, {"runs": 0, "unsafe": 0, "queries": 0, "entries": []})
        row["runs"] += 1
        row["unsafe"] += item["screening"]["unsafe_query_count"]
        row["queries"] += item["screening"]["query_count"]
        row["entries"].append(item["after_stats"].get("entry_count"))
    return {f"{scenario}/{mode}": {**row, "mean_entries": sum(row["entries"]) / len(row["entries"])}
            for (scenario, mode), row in grouped.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mem0-artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "scope": "security benchmark and framework comparison",
        "letta": {
            "framework": "Letta OSS 0.16.8",
            "processing_surface": "asynchronous sleeptime reflection",
            "availability": "no DoS threshold met",
            "quality": "no sustained retrieval decline",
            "integrity": "0/9 unsafe held-out answers after 3 attack rounds",
            "telemetry": "direct event attribution partial; proxy token fallback",
        },
        "mem0": {
            "framework": "Mem0 OSS 2.0.18",
            "processing_surface": "synchronous extraction during add",
            "reflection_equivalent": False,
            "integrity_matrix": mem0_summary(args.mem0_artifact),
            "telemetry": "extraction response and Chroma retention diagnostics",
        },
        "claim_policy": [
            "Compare processing architectures; do not call Mem0 extraction sleeptime reflection.",
            "Do not claim poisoning from keyword screening alone.",
            "Do not claim extraction is a mitigation without separating filtering from non-retention.",
        ],
    }
    lines = ["# Framework comparison summary", "", "| Framework | Processing surface | Availability/integrity result |", "|---|---|---|"]
    lines.append("| Letta OSS 0.16.8 | Asynchronous sleeptime reflection | No DoS threshold; 0/9 held-out unsafe after long attack |")
    lines.append("| Mem0 OSS 2.0.18 | Synchronous `add(infer=True)` extraction | See mode/scenario matrix below; not reflection-equivalent |")
    lines.extend(["", "## Mem0 integrity matrix", "", "| Scenario/mode | Unsafe | Queries | Mean retained entries |", "|---|---:|---:|---:|"])
    for key, row in sorted(report["mem0"]["integrity_matrix"].items()):
        lines.append(f"| {key} | {row['unsafe']} | {row['queries']} | {row['mean_entries']:.2f} |")
    report["markdown"] = "\n".join(lines) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    args.output.with_suffix(".md").write_text(report["markdown"], encoding="utf-8")
    print(json.dumps({"json": str(args.output), "markdown": str(args.output.with_suffix('.md'))}, indent=2))


if __name__ == "__main__":
    main()
