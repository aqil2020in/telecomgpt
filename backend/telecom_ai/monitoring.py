"""Monitoring and observability for orchestrator runs."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any


class RunMonitor:
    """Tracks latency, steps, errors per orchestrator invocation."""

    def __init__(self, *, session_id: str, query: str) -> None:
        self.session_id = session_id
        self.query = query[:200]
        self.started_at = datetime.now(timezone.utc).isoformat()
        self._t0 = time.perf_counter()
        self.steps: list[str] = []
        self.errors: list[dict] = []
        self.agent_timings: dict[str, float] = {}

    def record_step(self, step: str) -> None:
        self.steps.append(step)

    def record_error(self, agent: str, error: str) -> None:
        self.errors.append({"agent": agent, "error": error[:300], "ts": datetime.now(timezone.utc).isoformat()})

    def record_agent_timing(self, agent: str, seconds: float) -> None:
        self.agent_timings[agent] = round(seconds, 3)

    def finish(self, *, confidence: float | None = None, guardrail_issues: list | None = None) -> dict[str, Any]:
        elapsed = round(time.perf_counter() - self._t0, 3)
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "elapsed_sec": elapsed,
            "steps": self.steps,
            "errors": self.errors,
            "agent_timings": self.agent_timings,
            "confidence": confidence,
            "guardrail_issues": guardrail_issues or [],
            "status": "error" if self.errors else "ok",
        }


# In-process ring buffer for recent runs (dev/admin)
_RECENT_RUNS: list[dict] = []
_MAX_RUNS = 50


def store_run_summary(summary: dict) -> None:
    _RECENT_RUNS.append(summary)
    while len(_RECENT_RUNS) > _MAX_RUNS:
        _RECENT_RUNS.pop(0)


def recent_runs(limit: int = 20) -> list[dict]:
    return list(reversed(_RECENT_RUNS[-limit:]))
