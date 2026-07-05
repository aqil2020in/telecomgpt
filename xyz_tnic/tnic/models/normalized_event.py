"""Normalized telecom event model — common format for all uploaded sources."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NormalizedEvent(BaseModel):
    timestamp: str = ""
    cell_id: str = ""
    ue_id: str = ""
    source: str = ""
    domain: str = ""
    event: str = ""
    severity: str = "info"
    metadata: dict[str, Any] = Field(default_factory=dict)

    def is_failure(self) -> bool:
        sev = self.severity.lower()
        ev = self.event.upper()
        meta_result = str(self.metadata.get("result", "")).upper()
        fail_tokens = ("FAIL", "FAILURE", "DROP", "REJECT", "TIMEOUT", "CRITICAL", "MAJOR")
        return sev in ("fail", "failure", "critical", "major", "error") or any(
            t in ev or t in meta_result for t in fail_tokens
        )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
