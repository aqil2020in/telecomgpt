"""PM counter ingestion and KPI validation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from tnic.db.session import PMCounterRecord, get_session_factory, init_db
from tnic.logging_config import get_logger

log = get_logger(__name__)

COUNTER_ALIASES = {
    "ho_succ_rate": "ho_success_rate",
    "ho_prep_fail": "ho_prep_fail_rate",
    "rrc_reestab_fail": "rlf_rate",
    "qdrop": "call_drop_rate",
    "dl_bler": "bler",
    "avg_cqi": "cqi",
    "dl_throughput": "throughput_mbps",
    "prach_fail": "rach_msg1_fail_rate",
    "beam_fail_ratio": "beam_failure_ratio",
    "upf_lat": "upf_latency_ms",
}


def normalize_counter_name(name: str) -> str:
    key = name.strip().lower().replace(" ", "_").replace("-", "_")
    return COUNTER_ALIASES.get(key, key)


def ingest_pm_csv(path: str | Path, *, vendor: str = "generic") -> dict[str, Any]:
    """Ingest PM counter CSV: cell_id, counter_name, counter_value, period_start."""
    init_db()
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    cell_col = cols.get("cell_id") or cols.get("cell") or list(df.columns)[0]
    counter_col = cols.get("counter_name") or cols.get("counter") or list(df.columns)[1]
    value_col = cols.get("counter_value") or cols.get("value") or list(df.columns)[2]

    session = get_session_factory()()
    rows = 0
    cells: set[str] = set()
    kpi_agg: dict[str, list[float]] = {}

    try:
        for _, row in df.iterrows():
            cell_id = str(row[cell_col])
            counter = normalize_counter_name(str(row[counter_col]))
            value = float(row[value_col])
            cells.add(cell_id)
            kpi_agg.setdefault(counter, []).append(value)
            rec = PMCounterRecord(
                cell_id=cell_id,
                counter_name=counter,
                counter_value=value,
                vendor=vendor,
                period_start=datetime.utcnow(),
            )
            session.add(rec)
            rows += 1
        session.commit()
    finally:
        session.close()

    kpi_summary = {k: round(sum(v) / len(v), 2) for k, v in kpi_agg.items()}
    issues = validate_pm_kpis(kpi_summary)
    return {
        "ok": True,
        "rows_ingested": rows,
        "cells": sorted(cells),
        "kpi_summary": kpi_summary,
        "validation_issues": issues,
    }


def validate_pm_kpis(kpis: dict[str, Any]) -> list[str]:
    """Counter consistency and KPI derivation checks."""
    issues: list[str] = []
    ho_succ = kpis.get("ho_success_rate")
    ho_prep = kpis.get("ho_prep_fail_rate")
    if ho_succ is not None and ho_prep is not None and ho_succ + ho_prep > 100.5:
        issues.append("HO success + prep fail rates exceed 100% — counter definition mismatch")

    bler = kpis.get("bler")
    if bler is not None and bler > 100:
        issues.append("BLER > 100% — check if counter is ratio vs percentage")

    cqi = kpis.get("cqi")
    if cqi is not None and (cqi < 0 or cqi > 15):
        issues.append("CQI out of 3GPP range [0,15]")

    if kpis.get("ss_rsrp") is not None and kpis.get("ss_rsrp") > 0:
        issues.append("SS-RSRP positive — likely unit error (expect dBm negative)")

    rach = kpis.get("rach_success_rate")
    if rach is not None and rach > 100:
        issues.append("RACH success rate > 100% — normalize counter")

    return issues


def aggregate_cell_kpis(path: str | Path) -> dict[str, dict[str, float]]:
    """Pivot PM CSV to cell_id → KPI dict for RCA."""
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    cell_col = cols.get("cell_id") or cols.get("cell") or list(df.columns)[0]
    counter_col = cols.get("counter_name") or cols.get("counter") or list(df.columns)[1]
    value_col = cols.get("counter_value") or cols.get("value") or list(df.columns)[2]

    result: dict[str, dict[str, list[float]]] = {}
    for _, row in df.iterrows():
        cell = str(row[cell_col])
        counter = normalize_counter_name(str(row[counter_col]))
        val = float(row[value_col])
        result.setdefault(cell, {}).setdefault(counter, []).append(val)

    out: dict[str, dict[str, float]] = {}
    for cell, counters in result.items():
        out[cell] = {k: sum(v) / len(v) for k, v in counters.items()}
    return out
