"""PM counter integrity validation rules."""

from __future__ import annotations

from typing import Any

from tnic.rules.engine import RuleDefinition, RuleEngine, _get
from tnic.services.pm_ingestion import validate_pm_kpis


def _pm_validation_rules() -> list[RuleDefinition]:
    cat = "pm_validation"

    return [
        RuleDefinition(
            "pm_ho_rate_mismatch", cat, "HO rate counter mismatch",
            lambda k: (
                _get(k, "ho_success_rate") is not None
                and _get(k, "ho_prep_fail_rate") is not None
                and (_get(k, "ho_success_rate") + _get(k, "ho_prep_fail_rate")) > 100.5
            ),
            "HO success + prep fail rates exceed 100% — counter definition mismatch",
            0.70,
            ["Reconcile HO counter numerators/denominators", "Verify vendor KPI formula"],
            ["ho_success_rate", "ho_prep_fail_rate"],
        ),
        RuleDefinition(
            "pm_cqi_range", cat, "CQI out of range",
            lambda k: _get(k, "cqi") is not None and (_get(k, "cqi") < 0 or _get(k, "cqi") > 15),
            "CQI out of 3GPP range [0,15] — unit or scaling error",
            0.72,
            ["Check CQI aggregation formula", "Validate PM export mapping"],
            ["cqi"],
        ),
        RuleDefinition(
            "pm_bler_unit", cat, "BLER unit error",
            lambda k: _get(k, "bler") is not None and _get(k, "bler") > 100,
            "BLER > 100% — counter may be ratio vs percentage",
            0.71,
            ["Normalize BLER to percentage", "Check if raw BLER ratio exported as percent"],
            ["bler"],
        ),
        RuleDefinition(
            "pm_rsrp_unit", cat, "RSRP unit error",
            lambda k: _get(k, "ss_rsrp") is not None and _get(k, "ss_rsrp") > 0,
            "SS-RSRP positive — expect dBm negative values",
            0.73,
            ["Convert RSRP units to dBm", "Validate drive-test vs PM counter alignment"],
            ["ss_rsrp"],
        ),
        RuleDefinition(
            "pm_rach_rate", cat, "RACH rate out of range",
            lambda k: _get(k, "rach_success_rate") is not None and _get(k, "rach_success_rate") > 100,
            "RACH success rate > 100% — normalize counter",
            0.70,
            ["Verify RACH attempt denominator", "Check PM aggregation window"],
            ["rach_success_rate"],
        ),
    ]


class PMValidationRuleEngine(RuleEngine):
    """Combines explicit rules with validate_pm_kpis service checks."""

    def __init__(self):
        super().__init__("pm_validation", _pm_validation_rules())

    def evaluate(self, kpis: dict[str, Any]) -> list[dict[str, Any]]:
        findings = super().evaluate(kpis)
        existing = {f["rule_id"] for f in findings}
        for i, issue in enumerate(validate_pm_kpis(kpis)):
            rid = f"pm_validation_service_{i}"
            if rid not in existing:
                findings.append({
                    "rule_id": rid,
                    "category": "pm_validation",
                    "probable_cause": issue,
                    "confidence": 0.65,
                    "evidence": {},
                    "recommended_actions": [
                        "Reconcile PM counter definitions",
                        "Verify KPI derivation formula",
                    ],
                })
        return findings


PM_VALIDATION_RULE_ENGINE = PMValidationRuleEngine()
