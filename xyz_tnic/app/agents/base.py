"""Specialist agent base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models.schemas import AgentResult, KPIInput, RuleFinding


class BaseAgent(ABC):
    name: str = "base"
    issue_types: tuple[str, ...] = ()

    @abstractmethod
    def analyze(self, kpis: dict[str, Any], query: str = "") -> AgentResult:
        ...

    def _findings_to_result(self, findings: list[dict[str, Any]], summary: str = "") -> AgentResult:
        return AgentResult(
            agent=self.name,
            findings=[RuleFinding(**f) for f in findings],
            summary=summary or f"{self.name} completed with {len(findings)} finding(s).",
        )


def kpi_to_dict(kpis: KPIInput | dict[str, Any]) -> dict[str, Any]:
    if isinstance(kpis, dict):
        base = dict(kpis)
    else:
        base = kpis.model_dump(exclude_none=True)
        base.update(kpis.extra or {})
    return {k: v for k, v in base.items() if v is not None}
