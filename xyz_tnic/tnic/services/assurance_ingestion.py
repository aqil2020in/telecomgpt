"""Core assurance dataset ingestion — aggregate per-cell KPIs for RCA agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from tnic.datasets.loaders import (
    clear_loader_cache,
    load_alarm_events,
    load_anr_events,
    load_cell_configuration,
    load_gnb_syslog,
    load_neighbor_relations,
    load_vonr_sessions,
)
from tnic.datasets.models import AssuranceIngestResult
from tnic.services.config_baseline import audit_configuration
from tnic.services.gnb_syslog_parser import parse_syslog_text, parse_syslog_dataframe


def _safe_rate(num: float, den: float) -> float | None:
    if den <= 0:
        return None
    return round(100.0 * num / den, 2)


def _kpis_from_gnb_syslog(df: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    sub = df[df["cell_id"] == cell_id]
    if sub.empty:
        return {}
    total = len(sub)
    by_code = sub["event_code"].value_counts().to_dict() if "event_code" in sub.columns else {}
    by_module = sub["module"].value_counts().to_dict() if "module" in sub.columns else {}
    log_text = "\n".join(
        f"{r.get('module','')} {r.get('event_code','')} {r.get('message','')}"
        for _, r in sub.head(50).iterrows()
    )
    signatures = parse_syslog_dataframe(sub)
    return {
        "syslog_event_count": total,
        "syslog_event_codes": by_code,
        "syslog_modules": by_module,
        "syslog_text": log_text,
        "syslog_signatures": [s["rule_id"] for s in signatures],
        "syslog_ho_prep_fail_count": int(by_code.get("HO_PREP_FAIL", 0)),
        "syslog_xn_timeout_count": int(by_code.get("XN_TIMEOUT", 0)),
        "syslog_t310_count": int(by_code.get("T310_EXPIRY", 0)),
        "syslog_msg1_fail_count": int(by_code.get("MSG1_FAIL", 0)),
        "syslog_beam_overload_count": int(by_code.get("BEAM_OVERLOAD", 0)),
        "syslog_sip_timeout_count": int(by_code.get("SIP_TIMEOUT", 0)),
    }


def _kpis_from_cell_config(df: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    sub = df[df["cell_id"] == cell_id]
    if sub.empty:
        return {}
    row = sub.iloc[0]
    return {
        "pci": int(row["pci"]),
        "ho_a3_offset_db": float(row.get("a3_offset", row.get("ho_a3_offset_db", 0))),
        "ho_hysteresis_db": float(row.get("hysteresis", row.get("ho_hysteresis_db", 0))),
        "ho_time_to_trigger_ms": int(row.get("time_to_trigger", row.get("ho_ttt_ms", 160))),
        "nr_neighbor_count": int(row.get("neighbor_count", row.get("nr_neighbor_count", 0))),
        "tac": int(row.get("tac", 0)),
    }


def _kpis_from_neighbor_relations(df: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    sub = df[df["source_cell"] == cell_id]
    if sub.empty:
        return {}
    total = len(sub)
    missing = int((sub["relation_status"] == "MISSING").sum())
    active = int((sub["relation_status"] == "ACTIVE").sum())
    return {
        "nr_neighbor_count": max(active, 0),
        "missing_neighbor_count": missing,
        "neighbor_relation_total": total,
        "stale_neighbor_pct": _safe_rate(missing, total),
    }


def _kpis_from_anr_events(df: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    sub = df[df["cell_id"] == cell_id]
    if sub.empty:
        return {}
    total = len(sub)
    by_type = sub["event_type"].value_counts().to_dict()
    pci_conflicts = int(by_type.get("PCI_CONFLICT", 0))
    missing_nbr = int(by_type.get("MISSING_NEIGHBOR", 0))
    add_fail = int(by_type.get("ANR_ADD_FAIL", 0))
    return {
        "anr_event_count": total,
        "pci_conflict_count": pci_conflicts,
        "anr_pci_conflict_count": pci_conflicts,
        "anr_missing_neighbor_count": missing_nbr,
        "anr_add_fail_count": add_fail,
        "anr_blacklist_count": add_fail,
        "anr_event_types": by_type,
    }


def _kpis_from_vonr_sessions(df: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    sub = df[df["cell_id"] == cell_id]
    if sub.empty:
        return {}
    total = len(sub)
    drops = int((sub["result"] == "DROP").sum())
    success = int((sub["result"] == "SUCCESS").sum())
    by_cause = sub[sub["result"] == "DROP"]["cause"].value_counts().to_dict() if drops else {}
    ims_timeout = int(by_cause.get("IMS_TIMEOUT", 0))
    qos_fail = int(by_cause.get("QOS_FLOW_FAIL", 0))
    return {
        "vonr_session_count": total,
        "vonr_drop_rate": _safe_rate(drops, total),
        "vonr_setup_success_rate": _safe_rate(success, total),
        "drop_ims_pct": _safe_rate(ims_timeout + qos_fail, total),
        "ims_timeout_count": ims_timeout,
        "qos_flow_fail_count": qos_fail,
        "vonr_drop_causes": by_cause,
    }


def _kpis_from_alarm_events(df: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    sub = df[df["cell_id"] == cell_id]
    if sub.empty:
        return {}
    total = len(sub)
    by_name = sub["alarm_name"].value_counts().to_dict()
    by_sev = sub["severity"].value_counts().to_dict()
    critical = int(by_sev.get("CRITICAL", 0))
    major = int(by_sev.get("MAJOR", 0))
    transport_alarms = sum(v for k, v in by_name.items() if "transport" in k.lower() or "packet" in k.lower())
    hw_alarms = sum(v for k, v in by_name.items() if any(x in k.lower() for x in ("ptp", "sync", "beam", "du", "cu")))
    return {
        "active_alarm_count": total,
        "critical_alarm_count": critical,
        "alarm_severity_counts": by_sev,
        "alarm_name_counts": by_name,
        "transport_alarm_count": transport_alarms,
        "hw_alarm_count": hw_alarms,
        "active_alarms": ", ".join(f"{k}({v})" for k, v in list(by_name.items())[:5]),
        "alarm_severity": "CRITICAL" if critical else ("MAJOR" if major else "MINOR"),
        "transport_loss_rate": min(1.0, transport_alarms / max(total, 1)),
    }


def aggregate_assurance_kpis(cell_id: str) -> dict[str, Any]:
    """Merge all assurance dataset KPIs for a cell."""
    cid = cell_id.upper()
    merged: dict[str, Any] = {"cell_id": cid}
    sources: list[str] = []

    loaders = [
        ("gnb_syslog", load_gnb_syslog, _kpis_from_gnb_syslog),
        ("cell_configuration", load_cell_configuration, _kpis_from_cell_config),
        ("neighbor_relations", load_neighbor_relations, _kpis_from_neighbor_relations),
        ("anr_events", load_anr_events, _kpis_from_anr_events),
        ("vonr_sessions", load_vonr_sessions, _kpis_from_vonr_sessions),
        ("alarm_events", load_alarm_events, _kpis_from_alarm_events),
    ]
    for source, loader, fn in loaders:
        try:
            df = loader()
            kpis = fn(df, cid)
            if kpis:
                for k, v in kpis.items():
                    if k not in merged or merged.get(k) is None:
                        merged[k] = v
                sources.append(source)
        except FileNotFoundError:
            continue

    # PCI conflict from ANR events
    if merged.get("anr_pci_conflict_count", 0) > 0:
        merged["pci_conflict_count"] = merged["anr_pci_conflict_count"]

    # Config audit drift from cell_configuration
    drift = audit_configuration(merged)
    if drift:
        merged["config_drift_count"] = len(drift)
        merged["config_drift_params"] = [d["evidence"].get("parameter") for d in drift]

    merged["assurance_sources"] = sources
    return merged


def ingest_assurance_dataset(name: str, path: str | Path | None = None) -> AssuranceIngestResult:
    """Ingest and validate a single assurance dataset."""
    from tnic.datasets.validation import validate_dataset

    loader_map = {
        "gnb_syslog": load_gnb_syslog,
        "cell_configuration": load_cell_configuration,
        "neighbor_relations": load_neighbor_relations,
        "anr_events": load_anr_events,
        "vonr_sessions": load_vonr_sessions,
        "alarm_events": load_alarm_events,
    }
    if name not in loader_map:
        return AssuranceIngestResult(
            dataset=name, ok=False, rows_ingested=0,
            validation_issues=[f"Unknown assurance dataset: {name}"],
        )

    if path:
        clear_loader_cache()
        df = loader_map[name](str(path))
    else:
        try:
            df = loader_map[name]()
        except FileNotFoundError as e:
            return AssuranceIngestResult(
                dataset=name, ok=False, rows_ingested=0,
                validation_issues=[str(e)],
            )

    validation = validate_dataset(name)
    cells: list[str] = []
    if "cell_id" in df.columns:
        cells = sorted(df["cell_id"].unique().tolist())
    elif "source_cell" in df.columns:
        cells = sorted(df["source_cell"].unique().tolist())

    kpi_summary: dict[str, Any] = {}
    for cid in cells[:10]:
        kpi_summary[cid] = aggregate_assurance_kpis(cid)

    return AssuranceIngestResult(
        dataset=name,
        ok=validation.ok,
        rows_ingested=len(df),
        cells=cells,
        validation_issues=[i.message for i in validation.issues if i.severity == "error"],
        kpi_summary=kpi_summary,
    )


def ingest_all_assurance() -> dict[str, AssuranceIngestResult]:
    """Ingest all core assurance datasets."""
    names = [
        "gnb_syslog", "cell_configuration", "neighbor_relations",
        "anr_events", "vonr_sessions", "alarm_events",
    ]
    return {n: ingest_assurance_dataset(n) for n in names}
