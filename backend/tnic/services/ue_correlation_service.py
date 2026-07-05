"""UE protocol correlation — cross-agent evidence and confidence scoring."""

from __future__ import annotations

from typing import Any

from tnic.models.ue_rca_result import UERcaResult
from tnic.parsers.ue_trace_parser import UETraceEvent, UETraceParser
from tnic.rules.ue_rca_rules import build_ue_rca_from_event
from tnic.services.assurance_ingestion import aggregate_assurance_kpis


def compute_ue_confidence(
    *,
    has_ue: bool = True,
    has_gnb: bool = False,
    has_pm: bool = False,
    has_rf: bool = False,
    has_transport: bool = False,
) -> tuple[float, dict[str, bool]]:
    """Confidence per telecom RCA playbook."""
    factors = {
        "ue_trace": has_ue,
        "gnb_evidence": has_gnb,
        "pm_counters": has_pm,
        "rf_data": has_rf,
        "transport": has_transport,
    }
    if has_ue and has_gnb and has_pm and has_rf and has_transport:
        return 0.98, factors
    if has_ue and has_gnb and has_pm and has_rf:
        return 0.95, factors
    if has_ue and has_gnb and has_pm:
        return 0.90, factors
    if has_ue and has_gnb:
        return 0.80, factors
    return 0.60, factors


def _gnb_correlates(event: UETraceEvent, kpis: dict[str, Any]) -> bool:
    codes = kpis.get("syslog_event_codes") or {}
    layer_map = {
        "RACH": ("MSG1_FAIL", "RACH"),
        "RLF": ("T310_EXPIRY", "XN_TIMEOUT"),
        "MOBILITY": ("HO_PREP_FAIL", "XN_TIMEOUT"),
        "IMS": ("SIP_TIMEOUT",),
        "BEAM": ("BEAM_OVERLOAD",),
    }
    keys = layer_map.get(event.layer, ())
    return any(int(codes.get(k, 0)) > 0 for k in keys) or bool(kpis.get("syslog_signatures"))


def _pm_correlates(kpis: dict[str, Any], agents: list[str]) -> bool:
    pm_keys = (
        "ho_prep_fail_rate", "rach_success_rate", "rlf_rate", "vonr_drop_rate",
        "throughput_mbps", "call_drop_rate", "prb_utilization",
    )
    if any(kpis.get(k) is not None for k in pm_keys):
        return True
    return bool(kpis.get("assurance_sources"))


def _rf_correlates(kpis: dict[str, Any], scenario: str) -> bool:
    if kpis.get("ss_rsrp") is not None or kpis.get("ss_sinr") is not None:
        return True
    if kpis.get("syslog_event_count") or kpis.get("coverage_score"):
        return True
    return scenario in ("COVERAGE_HOLE", "INTERFERENCE", "MIB_DECODE_FAILURE", "T310_EXPIRY")


def _transport_correlates(kpis: dict[str, Any], scenario: str) -> bool:
    if (kpis.get("transport_alarm_count") or 0) > 0:
        return True
    if (kpis.get("backhaul_utilization") or 0) > 75:
        return True
    if (kpis.get("transport_loss_rate") or 0) > 0.3:
        return True
    return scenario in ("IMS_FAILURE", "VONR_DROP", "PDU_SESSION_FAILURE")


def correlate_ue_failure(
    event: UETraceEvent,
    cell_kpis: dict[str, Any] | None = None,
) -> UERcaResult:
    """Build UERcaResult with cross-agent correlation and confidence."""
    base = build_ue_rca_from_event(event)
    kpis = dict(cell_kpis or {})
    if not kpis.get("assurance_sources"):
        try:
            kpis.update(aggregate_assurance_kpis(event.cell_id))
        except Exception:
            pass

    scenario = base["scenario_key"]
    has_gnb = _gnb_correlates(event, kpis)
    has_pm = _pm_correlates(kpis, base["correlate_agents"])
    has_rf = _rf_correlates(kpis, scenario)
    has_transport = _transport_correlates(kpis, scenario)

    confidence, factors = compute_ue_confidence(
        has_ue=True,
        has_gnb=has_gnb,
        has_pm=has_pm,
        has_rf=has_rf,
        has_transport=has_transport,
    )

    evidence = list(base["evidence"])
    correlated: list[str] = list(base["correlate_agents"])
    secondary = base.get("secondary_root_cause") or ""

    if has_gnb:
        evidence.append(f"gNB syslog correlated: {kpis.get('syslog_signatures', kpis.get('syslog_event_codes', {}))}")
    if has_pm:
        evidence.append("PM counters available for cross-validation")
    if has_rf:
        rsrp = kpis.get("ss_rsrp")
        sinr = kpis.get("ss_sinr")
        if rsrp is not None:
            evidence.append(f"RF: RSRP={rsrp} dBm, SINR={sinr} dB")
    if has_transport:
        evidence.append(f"Transport alarm/loss correlated: alarms={kpis.get('transport_alarm_count', 0)}")

    # Secondary cause from cross-domain
    if has_gnb and not secondary:
        secondary = "gNB syslog confirms network-side failure signature"
    elif has_rf and scenario in ("COVERAGE_HOLE", "T310_EXPIRY", "MIB_DECODE_FAILURE"):
        secondary = "RF coverage/SINR supports UE-side failure classification"

    return UERcaResult(
        ue_id=event.ue_id,
        cell_id=event.cell_id,
        issue=base["issue"],
        failure_stage=base["failure_stage"],
        protocol_layer=base["protocol_layer"],
        primary_root_cause=base["primary_root_cause"],
        secondary_root_cause=secondary,
        evidence=evidence,
        recommendations=base["recommendations"],
        confidence=confidence,
        correlated_agents=correlated,
        confidence_factors=factors,
    )


def correlate_cell_ue_failures(
    cell_id: str,
    ue_id: str | None = None,
    cell_kpis: dict[str, Any] | None = None,
) -> list[UERcaResult]:
    """Analyze all UE failures for a cell (optionally filter by ue_id)."""
    parser = UETraceParser()
    if ue_id:
        events = parser.failures_for_ue(ue_id)
    else:
        events = parser.failures_for_cell(cell_id)
    kpis = cell_kpis
    if kpis is None:
        try:
            from tnic.datasets.kpi_service import compute_cell_kpis
            kpis = compute_cell_kpis(cell_id).kpis
        except Exception:
            kpis = {}
    return [correlate_ue_failure(ev, kpis) for ev in events]
