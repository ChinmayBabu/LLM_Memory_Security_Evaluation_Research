"""Creation of reproducibility manifests for benchmark runs."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def collect_environment() -> dict[str, Any]:
    """Collect environment facts that affect result reproducibility."""

    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "memory_bytes": psutil.virtual_memory().total,
        "git_commit": _git_commit(),
    }


def create_run_manifest(
    output_dir: str | Path,
    *,
    system: str,
    attack: str,
    intensity: str,
    seed: int,
    config: dict[str, Any],
    models: dict[str, Any],
) -> tuple[str, Path]:
    """Write a unique JSON manifest and return its run ID and path."""

    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:8]}"
    manifest = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "system": system,
        "attack": attack,
        "intensity": intensity,
        "seed": seed,
        "models": models,
        "config": config,
        "environment": collect_environment(),
    }
    run_dir = Path(output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    path = run_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return run_id, path
