"""gNB syslog rules — log signature matching for RCA."""

from __future__ import annotations

from typing import Any

from tnic.rules.engine import RuleEngine
from tnic.services.gnb_syslog_parser import parse_syslog_text


class GNBSyslogRuleEngine(RuleEngine):
    """Evaluates syslog signatures from query text or uploaded log excerpt."""

    def __init__(self):
        super().__init__("gnb_syslog", [])

    def evaluate(self, kpis: dict[str, Any]) -> list[dict[str, Any]]:
        text = kpis.get("syslog_text") or kpis.get("log_excerpt") or kpis.get("query_log") or ""
        if not text and kpis.get("query"):
            text = str(kpis.get("query", ""))
        findings = parse_syslog_text(str(text))
        for f in findings:
            f["category"] = "gnb_syslog"
        return findings


GNB_SYSLOG_RULE_ENGINE = GNBSyslogRuleEngine()
