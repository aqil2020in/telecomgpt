"""Base rule engine — evaluates KPI thresholds and returns findings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class RuleDefinition:
    rule_id: str
    category: str
    description: str
    condition: Callable[[dict[str, Any]], bool]
    probable_cause: str
    confidence: float
    actions: list[str] = field(default_factory=list)
    evidence_keys: list[str] = field(default_factory=list)


class RuleEngine:
    def __init__(self, category: str, rules: list[RuleDefinition] | None = None):
        self.category = category
        self.rules = rules or []

    def evaluate(self, kpis: dict[str, Any]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for rule in self.rules:
            try:
                if rule.condition(kpis):
                    evidence = {k: kpis[k] for k in rule.evidence_keys if k in kpis and kpis[k] is not None}
                    findings.append({
                        "rule_id": rule.rule_id,
                        "category": rule.category,
                        "probable_cause": rule.probable_cause,
                        "confidence": rule.confidence,
                        "evidence": evidence,
                        "recommended_actions": rule.actions,
                    })
            except (TypeError, KeyError):
                continue
        findings.sort(key=lambda x: x["confidence"], reverse=True)
        return findings


def _get(kpis: dict, key: str, default: float | None = None) -> float | None:
    val = kpis.get(key, default)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
