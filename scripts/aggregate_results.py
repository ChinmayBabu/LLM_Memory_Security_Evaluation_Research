"""Aggregate completed JSON artifacts while preserving raw evidence."""

from __future__ import annotations

import argparse
import glob
import json
import math
from pathlib import Path
from typing import Any

from mabench.analysis.statistics import summarize


def get_path(payload: dict[str, Any], path: str) -> Any:
    parts = path.split(".")

    def walk(value: Any, index: int) -> Any:
        if index == len(parts):
            return value
        part = parts[index]
        if part.endswith("[]"):
            key = part[:-2]
            if not isinstance(value, dict) or not isinstance(value.get(key), list):
                return None
            return [walk(item, index + 1) for item in value[key]]
        if not isinstance(value, dict) or part not in value:
            return None
        return walk(value[part], index + 1)

    return walk(payload, 0)


def numeric_value(payload: dict[str, Any], path: str) -> float:
    value = get_path(payload, path)
    if isinstance(value, list):
        values = [float(item) for item in value if math.isfinite(float(item))]
        if not values:
            raise ValueError("empty numeric list")
        return sum(values) / len(values)
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite value")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--glob", dest="pattern", required=True)
    parser.add_argument("--value", required=True, help="Dotted numeric field path")
    parser.add_argument("--group", action="append", default=[], help="Dotted grouping field; repeatable")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records, skipped = [], []
    for filename in sorted(glob.glob(args.pattern)):
        try:
            payload = json.loads(Path(filename).read_text(encoding="utf-8"))
            numeric = numeric_value(payload, args.value)
            records.append((filename, payload, numeric))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            skipped.append({"file": filename, "reason": str(exc)})
    groups: dict[str, list[float]] = {}
    labels: dict[str, dict[str, Any]] = {}
    for filename, payload, value in records:
        label = {path: get_path(payload, path) for path in args.group}
        key = json.dumps(label, sort_keys=True, default=str)
        groups.setdefault(key, []).append(value)
        labels[key] = label
    result = {
        "value_field": args.value, "group_fields": args.group,
        "included_files": [filename for filename, _, _ in records],
        "skipped_files": skipped,
        "groups": [{"group": labels[key], "statistics": summarize(values), "values": values}
                   for key, values in sorted(groups.items())],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "included": len(records), "skipped": len(skipped)}, indent=2))


if __name__ == "__main__":
    main()
