"""Runtime flags for memory-constrained hosts (e.g. Render 512MB). Set TELECOMGPT_LOW_MEMORY=0 on 2GB+."""

from __future__ import annotations

import os


def low_memory_mode() -> bool:
    return os.environ.get("TELECOMGPT_LOW_MEMORY", "0") == "1"


def vector_enabled() -> bool:
    if low_memory_mode():
        return False
    return os.environ.get("TELECOMGPT_VECTOR", "1") == "1"


def max_parallel_agents() -> int:
    default = "2" if low_memory_mode() else "8"
    return max(1, int(os.environ.get("TELECOMGPT_MAX_PARALLEL_AGENTS", default)))


def kaggle_max_rows() -> int:
    default = "800" if low_memory_mode() else "2000"
    return max(100, int(os.environ.get("TELECOMGPT_KAGGLE_MAX_ROWS", default)))
