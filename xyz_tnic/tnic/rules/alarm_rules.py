"""FM alarm correlation rules."""

from __future__ import annotations

from tnic.rules.engine import RuleDefinition, RuleEngine, _get


def _alarm_rules() -> list[RuleDefinition]:
    cat = "alarm"

    return [
        RuleDefinition(
            "alarm_critical_active", cat, "Critical alarm active",
            lambda k: (_get(k, "critical_alarm_count") or 0) > 0 or "critical" in str(k.get("alarm_severity", "")).lower(),
            "Critical FM alarm active — correlate with KPI degradation before RF tuning",
            0.88,
            ["Clear HW/transport alarm first", "Correlate alarm timestamp with PM spike"],
            ["critical_alarm_count", "alarm_severity"],
        ),
        RuleDefinition(
            "alarm_transport_link", cat, "Transport link alarm",
            lambda k: (
                (_get(k, "transport_alarm_count") or 0) > 0
                or any(a in str(k.get("active_alarms", "")).lower() for a in ("link down", "sctp", "backhaul", "n3"))
            ),
            "Transport link alarm — backhaul/fronthaul fault correlated with service impact",
            0.85,
            ["Restore transport link", "Verify GTP/SCTP after alarm clear"],
            ["transport_alarm_count", "active_alarms"],
        ),
        RuleDefinition(
            "alarm_du_cu", cat, "DU/CU hardware alarm",
            lambda k: (
                (_get(k, "hw_alarm_count") or 0) > 0
                or any(a in str(k.get("active_alarms", "")).lower() for a in ("du", "cu", "f1", "crash", "sync"))
            ),
            "DU/CU/F1 alarm — cell outage or degraded service from RAN HW",
            0.87,
            ["Check DU/CU pod status", "Restore F1/fronthaul", "Validate cell availability post-recovery"],
            ["hw_alarm_count", "active_alarms", "cell_availability"],
        ),
        RuleDefinition(
            "alarm_kpi_correlation", cat, "Alarm-KPI temporal correlation",
            lambda k: (
                (_get(k, "active_alarm_count") or 0) > 0
                and (
                    (_get(k, "call_drop_rate") or 0) > 2
                    or (_get(k, "ho_success_rate") or 100) < 95
                    or (_get(k, "cell_availability") or 100) < 99
                )
            ),
            "Active alarms temporally correlated with KPI degradation",
            0.83,
            ["Build alarm timeline vs KPI chart", "Prioritize root alarm over symptom KPI"],
            ["active_alarm_count", "call_drop_rate", "ho_success_rate", "cell_availability"],
        ),
    ]


ALARM_RULE_ENGINE = RuleEngine("alarm", _alarm_rules())
