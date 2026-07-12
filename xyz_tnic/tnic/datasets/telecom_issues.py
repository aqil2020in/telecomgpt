"""Unified telecom issues dataset — one CSV for all RCA domains."""

from __future__ import annotations

from typing import Any

import pandas as pd

from tnic.datasets.kpi_service import (
    _kpis_from_call_drop,
    _kpis_from_handover,
    _kpis_from_pm,
    _kpis_from_rach,
    _kpis_from_rlf,
    _kpis_from_throughput,
    _safe_rate,
)
from tnic.models.normalized_event import NormalizedEvent
from tnic.services.health_scoring import compute_health_score

ISSUE_DOMAINS = frozenset({
    "handover", "rlf", "rach", "call_drop", "throughput", "beamforming",
    "vonr", "anr", "gnb_syslog", "alarm", "config_audit", "ue_protocol",
    "pm", "neighbor", "transport",
})

SUCCESS_TOKENS = frozenset({"SUCCESS", "OK", "PASS", "CLEARED", "NORMAL"})
FAIL_TOKENS = frozenset({
    "FAIL", "FAILURE", "DROP", "REJECT", "TIMEOUT", "CRITICAL", "MAJOR",
    "ERROR", "DEGRADED", "WARN",
})

UNIFIED_COLUMNS = (
    "timestamp", "cell_id", "ue_id", "issue_domain", "event_type", "result",
    "cause", "rsrp", "sinr", "cqi", "target_cell", "source_cell",
    "dl_tp", "prb_util", "severity", "alarm_name", "module", "event_code",
    "message", "details", "beam_id", "beam_health_score", "beam_switch_rate",
)


def _norm_domain(value: str) -> str:
    d = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "ho": "handover", "handover_failure": "handover", "mobility": "handover",
        "radio_link_failure": "rlf", "access": "rach",
        "call_drops": "call_drop", "drops": "call_drop",
        "tp": "throughput", "beam": "beamforming", "beams": "beamforming",
        "voice": "vonr", "volte": "vonr", "ims": "vonr",
        "syslog": "gnb_syslog", "gnb": "gnb_syslog",
        "alarms": "alarm", "fm": "alarm",
        "config": "config_audit", "configuration": "config_audit",
        "ue_trace": "ue_protocol", "protocol": "ue_protocol",
        "pm_counters": "pm", "counters": "pm",
        "nbr": "neighbor", "relations": "neighbor",
    }
    return aliases.get(d, d)


def _is_success(result: str, event_type: str) -> bool:
    r = str(result or "").upper()
    e = str(event_type or "").upper()
    if r in SUCCESS_TOKENS:
        return True
    if r in FAIL_TOKENS:
        return False
    if e == "SUCCESS":
        return True
    return False


def _result_from_row(result: str, event_type: str, domain: str) -> str:
    r = str(result or "").strip().upper()
    if r:
        return r
    e = str(event_type or "").strip().upper()
    if e == "SUCCESS":
        return "SUCCESS"
    if domain in ("handover", "rach", "call_drop") and e and e != "SUCCESS":
        return "FAIL"
    if domain == "rlf":
        return "FAIL"
    if domain in ("vonr", "alarm", "gnb_syslog", "ue_protocol") and e:
        if any(t in e for t in ("DROP", "FAIL", "REJECT", "TIMEOUT")):
            return "FAIL"
    return "SUCCESS" if _is_success(r, e) else "FAIL"


def events_to_issues_dataframe(events: list[NormalizedEvent]) -> pd.DataFrame:
    """Convert normalized upload events back to unified telecom_issues rows."""
    rows: list[dict[str, Any]] = []
    for e in events:
        meta = e.metadata or {}
        domain = _norm_domain(e.domain or meta.get("issue_domain", "unknown"))
        event_type = (
            meta.get("event_type")
            or meta.get("failure_type")
            or meta.get("drop_type")
            or meta.get("msg_failure")
            or e.event
            or "EVENT"
        )
        result = _result_from_row(
            meta.get("result", ""),
            str(event_type),
            domain,
        )
        rows.append({
            "timestamp": e.timestamp or meta.get("timestamp", ""),
            "cell_id": e.cell_id or meta.get("cell_id", ""),
            "ue_id": e.ue_id or meta.get("ue_id", ""),
            "issue_domain": domain,
            "event_type": str(event_type).upper(),
            "result": result,
            "cause": meta.get("cause", ""),
            "rsrp": meta.get("rsrp", ""),
            "sinr": meta.get("sinr", ""),
            "cqi": meta.get("cqi", ""),
            "target_cell": meta.get("target_cell", ""),
            "source_cell": meta.get("source_cell", e.cell_id),
            "dl_tp": meta.get("dl_tp", ""),
            "prb_util": meta.get("prb_util", ""),
            "severity": e.severity or meta.get("severity", ""),
            "alarm_name": meta.get("alarm_name", ""),
            "module": meta.get("module", ""),
            "event_code": meta.get("event_code", ""),
            "message": meta.get("message", meta.get("raw_line", "")),
            "details": meta.get("details", ""),
            "beam_id": meta.get("beam_id", ""),
            "beam_health_score": meta.get("beam_health_score", ""),
            "beam_switch_rate": meta.get("beam_switch_rate", ""),
        })
    if not rows:
        return pd.DataFrame(columns=list(UNIFIED_COLUMNS))
    return pd.DataFrame(rows)


def _cell_slice(df: pd.DataFrame, cell_id: str) -> pd.DataFrame:
    cid = str(cell_id).upper()
    sub = df[df["cell_id"].astype(str).str.upper() == cid]
    ho_src = df[df["source_cell"].astype(str).str.upper() == cid] if "source_cell" in df.columns else sub
    return pd.concat([sub, ho_src]).drop_duplicates().reset_index(drop=True)


def _to_handover_df(sub: pd.DataFrame, cell_id: str) -> pd.DataFrame:
    rows = []
    for _, r in sub.iterrows():
        ft = str(r.get("event_type") or "EVENT").upper()
        rows.append({
            "source_cell": str(r.get("source_cell") or r.get("cell_id") or cell_id),
            "target_cell": str(r.get("target_cell") or ""),
            "ue_id": str(r.get("ue_id") or ""),
            "failure_type": "SUCCESS" if _is_success(str(r.get("result", "")), ft) else ft,
            "serving_rsrp": pd.to_numeric(r.get("rsrp"), errors="coerce"),
            "serving_sinr": pd.to_numeric(r.get("sinr"), errors="coerce"),
            "rsrp": pd.to_numeric(r.get("rsrp"), errors="coerce"),
            "sinr": pd.to_numeric(r.get("sinr"), errors="coerce"),
        })
    return pd.DataFrame(rows)


def _to_rlf_df(sub: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in sub.iterrows():
        rows.append({
            "cell_id": r.get("cell_id"),
            "ue_id": r.get("ue_id"),
            "cause": r.get("cause") or r.get("event_type") or "Unknown",
            "rsrp": pd.to_numeric(r.get("rsrp"), errors="coerce"),
            "sinr": pd.to_numeric(r.get("sinr"), errors="coerce"),
        })
    return pd.DataFrame(rows)


def _to_rach_df(sub: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in sub.iterrows():
        et = str(r.get("event_type") or "MSG1").upper()
        msg = et if et.startswith("MSG") else et
        if _is_success(str(r.get("result", "")), et):
            msg = "SUCCESS"
        rows.append({"cell_id": r.get("cell_id"), "ue_id": r.get("ue_id"), "msg_failure": msg})
    return pd.DataFrame(rows)


def _to_call_drop_df(sub: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in sub.iterrows():
        dt = str(r.get("event_type") or r.get("cause") or "Unknown")
        rows.append({"cell_id": r.get("cell_id"), "ue_id": r.get("ue_id"), "drop_type": dt})
    return pd.DataFrame(rows)


def _to_throughput_df(sub: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in sub.iterrows():
        issue = str(r.get("event_type") or r.get("cause") or "None")
        if _is_success(str(r.get("result", "")), issue):
            issue = "None"
        rows.append({
            "cell_id": r.get("cell_id"),
            "cqi": pd.to_numeric(r.get("cqi"), errors="coerce") or 0,
            "prb_util": pd.to_numeric(r.get("prb_util"), errors="coerce") or 0,
            "dl_tp": pd.to_numeric(r.get("dl_tp"), errors="coerce") or 0,
            "issue": issue,
        })
    return pd.DataFrame(rows)


def _kpis_from_beamforming(sub: pd.DataFrame) -> dict[str, Any]:
    if sub.empty:
        return {}
    scores = pd.to_numeric(sub.get("beam_health_score"), errors="coerce").dropna()
    switches = pd.to_numeric(sub.get("beam_switch_rate"), errors="coerce").dropna()
    fails = sub[~sub.apply(
        lambda r: _is_success(str(r.get("result", "")), str(r.get("event_type", ""))), axis=1
    )]
    total = len(sub)
    fail_n = len(fails)
    kpis: dict[str, Any] = {
        "beam_event_count": total,
        "beam_failure_ratio": _safe_rate(float(fail_n), float(total)),
    }
    if not scores.empty:
        kpis["beam_health_score_mean"] = round(float(scores.mean()), 1)
        kpis["beam_coverage_gap_pct"] = _safe_rate(float((scores < 70).sum()), float(len(scores)))
    if not switches.empty:
        kpis["beam_switch_rate"] = round(float(switches.mean()), 2)
        kpis["beam_instability_events"] = int((switches > 3).sum())
    return kpis


def _kpis_from_vonr(sub: pd.DataFrame) -> dict[str, Any]:
    if sub.empty:
        return {}
    total = len(sub)
    drops = sum(
        1 for _, r in sub.iterrows()
        if not _is_success(str(r.get("result", "")), str(r.get("event_type", "")))
    )
    return {
        "vonr_session_count": total,
        "vonr_drop_rate": _safe_rate(float(drops), float(total)),
        "vonr_fail_count": drops,
    }


def _kpis_from_anr(sub: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    if sub.empty:
        return {}
    conflicts = sum(1 for _, r in sub.iterrows() if "PCI" in str(r.get("event_type", "")).upper())
    missing = sum(1 for _, r in sub.iterrows() if "MISSING" in str(r.get("event_type", "")).upper())
    return {
        "anr_event_count": len(sub),
        "anr_pci_conflict_count": conflicts,
        "pci_conflict_count": conflicts,
        "missing_neighbor_count": missing,
    }


def _kpis_from_alarm(sub: pd.DataFrame) -> dict[str, Any]:
    if sub.empty:
        return {}
    critical = sum(1 for _, r in sub.iterrows() if str(r.get("severity", "")).upper() in ("CRITICAL", "MAJOR"))
    return {
        "alarm_event_count": len(sub),
        "active_alarm_count": len(sub),
        "critical_alarm_count": critical,
    }


def _kpis_from_syslog(sub: pd.DataFrame) -> dict[str, Any]:
    if sub.empty:
        return {}
    codes = sub["event_type"].astype(str).value_counts().to_dict() if "event_type" in sub.columns else {}
    fails = sub[~sub.apply(
        lambda r: _is_success(str(r.get("result", "")), str(r.get("event_type", ""))), axis=1
    )]
    text = "\n".join(str(r.get("message") or r.get("event_type") or "") for _, r in sub.head(50).iterrows())
    return {
        "syslog_event_count": len(sub),
        "syslog_event_codes": codes,
        "syslog_text": text,
        "syslog_ho_prep_fail_count": sum(
            1 for _, r in sub.iterrows() if "HO_PREP" in str(r.get("event_type", "")).upper()
        ),
        "syslog_signatures": [str(r.get("event_type")) for _, r in fails.head(20).iterrows()],
    }


def aggregate_kpis_from_issues_df(df: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    """Merge all issue domains for one cell using the same math as kpi_service."""
    if df.empty:
        return {"cell_id": cell_id}

    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    if "issue_domain" not in df.columns:
        return {"cell_id": cell_id}

    df["issue_domain"] = df["issue_domain"].map(_norm_domain)
    sub = _cell_slice(df, cell_id)
    merged: dict[str, Any] = {"cell_id": cell_id.upper()}
    sources: list[str] = []

    domain_groups = sub.groupby("issue_domain")
    for domain, grp in domain_groups:
        if domain == "handover":
            ho_df = _to_handover_df(grp, cell_id)
            k = _kpis_from_handover(ho_df, cell_id)
        elif domain == "rlf":
            k = _kpis_from_rlf(_to_rlf_df(grp), cell_id)
        elif domain == "rach":
            k = _kpis_from_rach(_to_rach_df(grp), cell_id)
        elif domain == "call_drop":
            ho_n = merged.get("ho_event_count")
            k = _kpis_from_call_drop(_to_call_drop_df(grp), cell_id, float(ho_n) if ho_n else None)
        elif domain == "throughput":
            k = _kpis_from_throughput(_to_throughput_df(grp), cell_id)
        elif domain == "beamforming":
            k = _kpis_from_beamforming(grp)
        elif domain == "vonr":
            k = _kpis_from_vonr(grp)
        elif domain == "anr":
            k = _kpis_from_anr(grp, cell_id)
        elif domain == "alarm":
            k = _kpis_from_alarm(grp)
        elif domain == "gnb_syslog":
            k = _kpis_from_syslog(grp)
        elif domain == "pm":
            pm_rows = []
            for _, r in grp.iterrows():
                pm_rows.append({
                    "cell_id": cell_id,
                    "ho_attempt": 1,
                    "rach_attempt": 1,
                    "ho_success": 1 if _is_success(str(r.get("result", "")), str(r.get("event_type", ""))) else 0,
                    "rach_success": 1 if _is_success(str(r.get("result", "")), str(r.get("event_type", ""))) else 0,
                    "dl_tp": float(r.get("dl_tp") or 0),
                    "ul_tp": 0,
                    "cqi": float(r.get("cqi") or 0),
                })
            k = _kpis_from_pm(pd.DataFrame(pm_rows), cell_id) if pm_rows else {}
        else:
            k = {"event_count": len(grp)}

        if k:
            for key, val in k.items():
                if val is not None and (key not in merged or merged.get(key) is None):
                    merged[key] = val
            sources.append(domain)

    merged["telecom_issues_sources"] = sources
    merged["telecom_issues_event_count"] = len(sub)
    health = compute_health_score(merged)
    merged["health_score"] = health["overall_score"]
    return merged


def aggregate_kpis_from_events(events: list[NormalizedEvent], cell_id: str) -> dict[str, Any]:
    """Aggregate KPIs from normalized telecom_issues upload events."""
    df = events_to_issues_dataframe(events)
    return aggregate_kpis_from_issues_df(df, cell_id)


def detect_key_issues(
    kpis: dict[str, Any],
    events: list[NormalizedEvent] | None = None,
) -> list[dict[str, Any]]:
    """Rank dominant telecom issues for RCA report summary."""
    issues: list[dict[str, Any]] = []

    checks = [
        ("handover", "Handover degradation", "ho_success_rate", "lt", 95,
         lambda v: f"HO success rate {v}% (target ≥95%)"),
        ("handover", "HO preparation failures", "ho_prep_fail_rate", "gt", 5,
         lambda v: f"HO prep fail rate {v}%"),
        ("handover", "Xn interface failures", "ho_xn_fail_rate", "gt", 3,
         lambda v: f"Xn HO fail rate {v}%"),
        ("rlf", "Radio link failures", "rlf_rate", "gt", 2,
         lambda v: f"RLF rate {v}%"),
        ("rlf", "Post-HO RLF", "rlf_post_ho_pct", "gt", 20,
         lambda v: f"Post-HO RLF {v}% of RLF events"),
        ("rach", "RACH access failures", "rach_success_rate", "lt", 92,
         lambda v: f"RACH success {v}%"),
        ("call_drop", "Call drops", "call_drop_rate", "gt", 2,
         lambda v: f"Call drop rate {v}%"),
        ("throughput", "Throughput degradation", "throughput_mbps", "lt", 50,
         lambda v: f"Mean throughput {v} Mbps"),
        ("beamforming", "Beam failures", "beam_failure_ratio", "gt", 15,
         lambda v: f"Beam failure ratio {v}%"),
        ("vonr", "VoNR drops", "vonr_drop_rate", "gt", 2,
         lambda v: f"VoNR drop rate {v}%"),
        ("anr", "PCI / neighbor issues", "anr_pci_conflict_count", "gt", 0,
         lambda v: f"{int(v)} PCI conflict events"),
        ("alarm", "Active alarms", "critical_alarm_count", "gt", 0,
         lambda v: f"{int(v)} critical/major alarms"),
        ("gnb_syslog", "Syslog HO/RLF signatures", "syslog_ho_prep_fail_count", "gt", 0,
         lambda v: f"{int(v)} HO prep fail syslog events"),
    ]

    for domain, title, key, op, threshold, fmt in checks:
        val = kpis.get(key)
        if val is None:
            continue
        try:
            num = float(val)
        except (TypeError, ValueError):
            continue
        hit = (num < threshold) if op == "lt" else (num > threshold)
        if hit:
            issues.append({
                "domain": domain,
                "title": title,
                "metric": key,
                "value": num,
                "summary": fmt(num),
                "severity": "high" if (op == "gt" and num > threshold * 2) or (op == "lt" and num < threshold * 0.8) else "medium",
            })

    if events:
        by_domain: dict[str, int] = {}
        fail_by_domain: dict[str, int] = {}
        for e in events:
            d = _norm_domain(e.domain or e.metadata.get("issue_domain", ""))
            if not d:
                continue
            by_domain[d] = by_domain.get(d, 0) + 1
            if e.is_failure():
                fail_by_domain[d] = fail_by_domain.get(d, 0) + 1
        for d, fails in sorted(fail_by_domain.items(), key=lambda x: -x[1])[:5]:
            if fails and not any(i["domain"] == d for i in issues):
                issues.append({
                    "domain": d,
                    "title": f"{d.replace('_', ' ').title()} events",
                    "metric": "failure_count",
                    "value": fails,
                    "summary": f"{fails} failure events of {by_domain.get(d, fails)} total",
                    "severity": "high" if fails >= 10 else "medium",
                })

    issues.sort(key=lambda x: (0 if x["severity"] == "high" else 1, -float(x.get("value", 0))))
    return issues[:12]


def build_rca_query_from_issues(key_issues: list[dict[str, Any]], cell_id: str) -> str:
    """Auto-generate RCA query from detected key issues."""
    if not key_issues:
        return f"telecom RCA all domains cell {cell_id}"
    domains = sorted({i["domain"] for i in key_issues[:4]})
    focus = " ".join(domains)
    return f"root cause analysis {focus} cell {cell_id}"
