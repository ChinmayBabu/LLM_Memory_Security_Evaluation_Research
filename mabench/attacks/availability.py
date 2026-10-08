"""Concurrent availability workload and deterministic summary helpers."""

from __future__ import annotations

import statistics
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from typing import Any, Callable


def percentile(values: list[float], percentile_rank: float) -> float | None:
    """Return a linear-interpolated percentile without a third-party dependency."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile_rank / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def summarize_requests(requests: list[dict[str, Any]], duration_s: float) -> dict[str, Any]:
    """Summarize successful and failed request observations."""
    latencies = [float(item["latency_ms"]) for item in requests if item.get("ok")]
    failures = [item for item in requests if not item.get("ok")]
    completed = len(latencies)
    total = len(requests)
    return {
        "requests_total": total,
        "requests_completed": completed,
        "requests_failed": len(failures),
        "error_rate": len(failures) / total if total else 0.0,
        "throughput_rps": completed / duration_s if duration_s > 0 else None,
        "latency_ms": {
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "p99": percentile(latencies, 99),
            "mean": statistics.fmean(latencies) if latencies else None,
        },
        "failures": failures,
    }


def run_concurrent_requests(
    jobs: list[dict[str, Any]],
    request_fn: Callable[[dict[str, Any]], Any],
    *,
    max_workers: int,
    timeout_s: float,
) -> list[dict[str, Any]]:
    """Run bounded jobs concurrently and preserve one result per submitted job."""
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(request_fn, job): job for job in jobs}
        completed_ids: set[str] = set()
        try:
            completed = as_completed(futures, timeout=timeout_s)
            for future in completed:
                job = futures[future]
                completed_ids.add(job["request_id"])
                request_started = float(job.get("started_perf", started))
                try:
                    future.result()
                    results.append({
                        "request_id": job["request_id"],
                        "session_id": job["session_id"],
                        "role": job["role"],
                        "ok": True,
                        "latency_ms": round((time.perf_counter() - request_started) * 1000, 3),
                    })
                except Exception as exc:  # preserve failures as data
                    results.append({
                        "request_id": job["request_id"],
                        "session_id": job["session_id"],
                        "role": job["role"],
                        "ok": False,
                        "latency_ms": round((time.perf_counter() - request_started) * 1000, 3),
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:500],
                    })
        except TimeoutError:
            for job in jobs:
                if job["request_id"] not in completed_ids:
                    results.append({
                        "request_id": job["request_id"],
                        "session_id": job["session_id"],
                        "role": job["role"],
                        "ok": False,
                        "latency_ms": round(timeout_s * 1000, 3),
                        "error_type": "TimeoutError",
                        "error": f"request batch exceeded {timeout_s}s",
                    })
    return results
