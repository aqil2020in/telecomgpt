"""Bridge normalized events to KPI dicts consumed by existing RCA agents."""

from __future__ import annotations

from collections import Counter
from typing import Any

from tnic.models.normalized_event import NormalizedEvent


def _safe_rate(num: float, den: float) -> float | None:
    if den <= 0:
        return None
    return round(100.0 * num / den, 2)


def kpis_from_events(events: list[NormalizedEvent], cell_id: str | None = None) -> dict[str, Any]:
    """Aggregate normalized events into the flat KPI dict agents expect."""
    if not events:
        return {"cell_id": cell_id or ""}

    cid = cell_id or next((e.cell_id for e in events if e.cell_id), "")
    kpis: dict[str, Any] = {"cell_id": cid, "event_sources": sorted({e.source for e in events})}
    kpis["normalized_event_count"] = len(events)
    kpis["normalized_failure_count"] = sum(1 for e in events if e.is_failure())
    kpis["assurance_sources"] = sorted({e.domain for e in events if e.domain})

    by_domain = Counter(e.domain for e in events)
    kpis["event_domains"] = dict(by_domain)

    # UE protocol
    ue_events = [e for e in events if e.domain == "ue_protocol"]
    if ue_events:
        kpis["ue_trace_event_count"] = len(ue_events)
        kpis["ue_trace_failure_count"] = sum(1 for e in ue_events if e.is_failure())
        kpis["ue_trace_failures"] = [
            {"ue_id": e.ue_id, "event": e.event, "cause": e.metadata.get("cause", "")}
            for e in ue_events if e.is_failure()
        ][:20]

    # gNB syslog
    syslog_events = [e for e in events if e.domain == "gnb_syslog"]
    if syslog_events:
        kpis["syslog_event_count"] = len(syslog_events)
        codes = Counter(e.event for e in syslog_events)
        kpis["syslog_event_codes"] = dict(codes)
        kpis["syslog_signatures"] = [e.event for e in syslog_events if e.is_failure()][:20]
        kpis["syslog_text"] = "\n".join(
            e.metadata.get("raw_line") or e.metadata.get("probable_cause") or e.event
            for e in syslog_events[:50]
        )
        kpis["syslog_ho_prep_fail_count"] = sum(
            1 for e in syslog_events if "HO_PREP" in e.event or "HO_PREP" in str(e.metadata)
        )
        kpis["syslog_t310_count"] = sum(1 for e in syslog_events if "T310" in e.event)

    # RF
    rf_events = [e for e in events if e.domain == "rf_coverage"]
    rsrp_vals = []
    sinr_vals = []
    for e in rf_events:
        if e.metadata.get("rsrp"):
            try:
                rsrp_vals.append(float(e.metadata["rsrp"]))
            except (TypeError, ValueError):
                pass
        if e.metadata.get("sinr"):
            try:
                sinr_vals.append(float(e.metadata["sinr"]))
            except (TypeError, ValueError):
                pass
    if rsrp_vals:
        kpis["ss_rsrp"] = round(sum(rsrp_vals) / len(rsrp_vals), 1)
    if sinr_vals:
        kpis["ss_sinr"] = round(sum(sinr_vals) / len(sinr_vals), 1)

    # PM counters
    pm_events = [e for e in events if e.domain == "pm"]
    for e in pm_events:
        name = e.event.lower().replace(" ", "_")
        try:
            kpis[name] = float(e.metadata.get("counter_value") or e.metadata.get("value") or 0)
        except (TypeError, ValueError):
            pass

    # Alarms
    alarm_events = [e for e in events if e.domain == "alarm"]
    if alarm_events:
        kpis["alarm_event_count"] = len(alarm_events)
        kpis["critical_alarm_count"] = sum(
            1 for e in alarm_events if e.severity in ("critical", "major", "fail")
        )

    # VoNR
    vonr_events = [e for e in events if e.domain == "vonr"]
    if vonr_events:
        fails = sum(1 for e in vonr_events if e.is_failure())
        kpis["vonr_session_count"] = len(vonr_events)
        kpis["vonr_drop_rate"] = _safe_rate(fails, len(vonr_events))

    # Mobility / HO from events
    ho_fails = sum(
        1 for e in events
        if "HO" in e.event and e.is_failure()
    )
    ho_total = sum(1 for e in events if "HO" in e.event)
    if ho_total:
        kpis["ho_event_count"] = ho_total
        kpis["ho_prep_fail_rate"] = _safe_rate(ho_fails, ho_total)

    # RACH
    rach_fails = sum(1 for e in events if ("RACH" in e.event or "MSG1" in e.event) and e.is_failure())
    rach_total = sum(1 for e in events if "RACH" in e.event or "MSG1" in e.event)
    if rach_total:
        kpis["rach_event_count"] = rach_total
        kpis["rach_success_rate"] = _safe_rate(rach_total - rach_fails, rach_total)

    # RLF
    rlf_events = [e for e in events if "RLF" in e.event or "T310" in e.event]
    if rlf_events:
        kpis["rlf_event_count"] = len(rlf_events)

    # Transport
    transport_events = [e for e in events if e.domain == "transport"]
    if transport_events:
        kpis["transport_alarm_count"] = sum(1 for e in transport_events if e.is_failure())

    # Config / neighbor
    if any(e.domain == "config_audit" for e in events):
        kpis["config_event_count"] = sum(1 for e in events if e.domain == "config_audit")
    if any(e.domain == "anr" for e in events):
        kpis["anr_event_count"] = sum(1 for e in events if e.domain == "anr")

    return kpis


def merge_kpis(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for k, v in overlay.items():
        if v is not None and v != "" and v != [] and v != {}:
            merged[k] = v
    return merged
