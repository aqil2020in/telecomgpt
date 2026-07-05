"""Configuration audit rules — CM parameter drift vs golden baseline."""

from __future__ import annotations

from typing import Any

from tnic.rules.engine import RuleEngine
from tnic.services.config_baseline import audit_configuration


class ConfigAuditRuleEngine(RuleEngine):
    """Wraps config_baseline audit as a rule engine."""

    def __init__(self):
        super().__init__("config_audit", [])

    def evaluate(self, kpis: dict[str, Any]) -> list[dict[str, Any]]:
        return audit_configuration(kpis)


CONFIG_AUDIT_RULE_ENGINE = ConfigAuditRuleEngine()
