"""UE Protocol Correlation Agent result model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UERcaResult(BaseModel):
    ue_id: str = ""
    cell_id: str = ""
    issue: str = ""
    failure_stage: str = ""
    protocol_layer: str = ""
    primary_root_cause: str = ""
    secondary_root_cause: str = ""
    evidence: list[str | dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    correlated_agents: list[str] = Field(default_factory=list)
    confidence_factors: dict[str, bool] = Field(default_factory=dict)

    def to_finding_dict(self) -> dict[str, Any]:
        """Convert to RuleFinding-compatible dict for Master RCA."""
        return {
            "rule_id": f"ue_protocol_{self.issue.lower().replace(' ', '_')[:40]}",
            "category": "ue_protocol",
            "probable_cause": (
                f"[UE Trace] {self.issue} at {self.failure_stage} ({self.protocol_layer}) — "
                f"{self.primary_root_cause}"
            ),
            "confidence": self.confidence,
            "evidence": {
                "ue_id": self.ue_id,
                "cell_id": self.cell_id,
                "failure_stage": self.failure_stage,
                "protocol_layer": self.protocol_layer,
                "primary_root_cause": self.primary_root_cause,
                "secondary_root_cause": self.secondary_root_cause,
                "trace_evidence": self.evidence,
                "correlated_agents": self.correlated_agents,
                "confidence_factors": self.confidence_factors,
            },
            "recommended_actions": self.recommendations,
        }
