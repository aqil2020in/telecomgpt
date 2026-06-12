"""In-process async job queue for long /ask requests (charts, PPT, eval)."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

_MAX_JOBS = 200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Job:
    id: str
    query: str
    status: str  # queued | running | completed | failed
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    trace: bool = False
    result: dict[str, Any] | None = None
    error: str | None = None


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, query: str, *, trace: bool = False) -> str:
        job_id = uuid.uuid4().hex[:16]
        with self._lock:
            self._jobs[job_id] = Job(
                id=job_id,
                query=query,
                status="queued",
                trace=trace,
            )
            self._prune_locked()
        return job_id

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def run_in_background(self, job_id: str, fn: Callable[[], dict]) -> None:
        def _worker() -> None:
            self._set_status(job_id, "running")
            try:
                result = fn()
                self._complete(job_id, result)
            except Exception as exc:
                self._fail(job_id, str(exc)[:500])

        threading.Thread(target=_worker, name=f"ask-job-{job_id}", daemon=True).start()

    def _set_status(self, job_id: str, status: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = status
                job.updated_at = _now()

    def _complete(self, job_id: str, result: dict) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "completed"
                job.result = result
                job.updated_at = _now()

    def _fail(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "failed"
                job.error = error
                job.updated_at = _now()

    def _prune_locked(self) -> None:
        if len(self._jobs) <= _MAX_JOBS:
            return
        ordered = sorted(self._jobs.values(), key=lambda j: j.created_at)
        for job in ordered[: len(self._jobs) - _MAX_JOBS]:
            self._jobs.pop(job.id, None)


job_store = JobStore()
