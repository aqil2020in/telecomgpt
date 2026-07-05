"""Configuration baseline audit — golden-parameter validation for RCA."""

from __future__ import annotations

from typing import Any

# Golden config ranges per 3GPP / operator NPI practice (demo baselines)
CONFIG_BASELINE: dict[str, dict[str, Any]] = {
    "ho_a3_offset_db": {"min": -6, "max": 6, "domain": "mobility", "fix": "Set A3 offset within -6..+6 dB per neighbor plan"},
    "ho_time_to_trigger_ms": {"min": 40, "max": 512, "domain": "mobility", "fix": "TTT typically 160–320 ms for urban; avoid < 40 ms"},
    "ho_hysteresis_db": {"min": 0, "max": 6, "domain": "mobility", "fix": "Increase hysteresis to reduce ping-pong (2–4 dB typical)"},
    "prach_config_index": {"min": 0, "max": 255, "domain": "accessibility", "fix": "Align prach-ConfigurationIndex with PCI/PRACH plan"},
    "p0_nominal_pusch": {"min": -126, "max": 24, "domain": "throughput", "fix": "Audit UL power control P0 and alpha"},
    "q_rxlevmin_dbm": {"min": -140, "max": -44, "domain": "coverage", "fix": "q-RxLevMin too high blocks edge UEs — review cell selection"},
    "q_qualmin_db": {"min": -43, "max": 0, "domain": "coverage", "fix": "q-QualMin impacts cell reselection — align with SINR targets"},
    "vonr_5qi_profile_present": {"equals": 1, "domain": "vonr", "fix": "Enable 5QI-1 and 5QI-65 profiles on SMF/UPF for VoNR"},
    "nr_neighbor_count": {"min": 3, "max": 32, "domain": "mobility", "fix": "ANR: ensure ≥3 intra-frequency neighbors; add missing NCR"},
    "pci_mod3_collision": {"max": 0, "domain": "mobility", "fix": "Resolve PCI mod-3 collision with neighbor PCI replan or ANR"},
}


def audit_configuration(kpis: dict[str, Any]) -> list[dict[str, Any]]:
    """Return config audit findings for parameters present in KPI bundle."""
    findings: list[dict[str, Any]] = []
    for param, spec in CONFIG_BASELINE.items():
        val = kpis.get(param)
        if val is None:
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            if "equals" in spec and val != spec["equals"]:
                findings.append(_audit_finding(param, val, spec, "value mismatch"))
            continue
        if "equals" in spec and v != float(spec["equals"]):
            findings.append(_audit_finding(param, v, spec, f"expected {spec['equals']}, got {v}"))
        if "min" in spec and v < float(spec["min"]):
            findings.append(_audit_finding(param, v, spec, f"below min {spec['min']}"))
        if "max" in spec and v > float(spec["max"]):
            findings.append(_audit_finding(param, v, spec, f"above max {spec['max']}"))
    findings.sort(key=lambda x: x["confidence"], reverse=True)
    return findings


def _audit_finding(param: str, val: Any, spec: dict, detail: str) -> dict[str, Any]:
    return {
        "rule_id": f"cfg_audit_{param}",
        "category": "config_audit",
        "probable_cause": f"Configuration drift: {param} — {detail}",
        "confidence": 0.81,
        "evidence": {"parameter": param, "value": val, "domain": spec.get("domain"), "detail": detail},
        "recommended_actions": [spec.get("fix", "Restore golden configuration")],
    }
