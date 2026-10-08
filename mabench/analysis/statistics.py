"""Deterministic statistics used by reflection benchmark reports."""

from __future__ import annotations

import math
import random
import statistics
from typing import Iterable


def bootstrap_mean_ci(values: Iterable[float], *, confidence: float = .95, resamples: int = 2000, seed: int = 20260830) -> dict[str, float | None]:
    values = [float(value) for value in values]
    if not values:
        return {"mean": None, "lower": None, "upper": None}
    rng = random.Random(seed)
    means = [sum(rng.choice(values) for _ in values) / len(values) for _ in range(resamples)]
    means.sort()
    alpha = (1 - confidence) / 2
    return {"mean": sum(values) / len(values), "lower": means[max(0, math.floor(alpha * resamples))], "upper": means[min(resamples - 1, math.ceil((1 - alpha) * resamples) - 1)]}


def paired_differences(left: Iterable[float], right: Iterable[float]) -> list[float]:
    pairs = list(zip(left, right))
    if not pairs:
        return []
    return [float(a) - float(b) for a, b in pairs]


def summarize(values: Iterable[float], *, seed: int = 20260830) -> dict[str, object]:
    """Return descriptive statistics and a deterministic bootstrap CI."""
    clean = [float(value) for value in values if math.isfinite(float(value))]
    if not clean:
        return {"n": 0, "mean": None, "median": None, "stdev": None,
                "p50": None, "p95": None, "p99": None,
                "bootstrap_mean_ci": bootstrap_mean_ci([], seed=seed)}
    ordered = sorted(clean)

    def percentile(p: float) -> float:
        position = (len(ordered) - 1) * p
        lower, upper = math.floor(position), math.ceil(position)
        if lower == upper:
            return ordered[lower]
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    return {
        "n": len(clean), "mean": statistics.fmean(clean),
        "median": statistics.median(clean),
        "stdev": statistics.stdev(clean) if len(clean) > 1 else 0.0,
        "p50": percentile(.50), "p95": percentile(.95), "p99": percentile(.99),
        "bootstrap_mean_ci": bootstrap_mean_ci(clean, seed=seed),
    }
