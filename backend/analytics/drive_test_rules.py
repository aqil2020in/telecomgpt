"""Drive-test SLA rule engine."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .csv_tools import detect_rf_columns, load_csv_path

_DEFAULT_RULES = {
    "rsrp_min_dbm": -110,
    "rsrq_min_db": -15,
    "latency_max_ms": 50,
    "throughput_min_mbps": 10,
    "packet_loss_max_pct": 1.0,
}


def _col(df: pd.DataFrame, rf: dict, key: str, *aliases: str) -> str | None:
    if rf.get(key):
        return rf[key]
    lower = {str(c).lower(): str(c) for c in df.columns}
    for a in aliases:
        if a.lower() in lower:
            return lower[a.lower()]
    return None


def run_drive_test_rules(path: str, rules: dict[str, float] | None = None) -> dict[str, Any]:
    df = load_csv_path(path)
    rf = detect_rf_columns(df)
    r = {**_DEFAULT_RULES, **(rules or {})}
    results: list[dict] = []
    n = len(df) or 1

    rsrp = _col(df, rf, "rsrp", "rsrp_dbm", "signal strength (dbm)", "signal strength")
    if rsrp and pd.api.types.is_numeric_dtype(df[rsrp]):
        fail = int((df[rsrp] < r["rsrp_min_dbm"]).sum())
        results.append({"rule": "RSRP", "threshold": f">= {r['rsrp_min_dbm']} dBm", "fail_rows": fail, "fail_pct": round(100 * fail / n, 2)})

    rsrq = _col(df, rf, "rsrq", "rsrq_db")
    if rsrq and pd.api.types.is_numeric_dtype(df[rsrq]):
        fail = int((df[rsrq] < r["rsrq_min_db"]).sum())
        results.append({"rule": "RSRQ", "threshold": f">= {r['rsrq_min_db']} dB", "fail_rows": fail, "fail_pct": round(100 * fail / n, 2)})

    lat = _col(df, rf, "latency", "latency_ms", "latency (ms)")
    if lat and pd.api.types.is_numeric_dtype(df[lat]):
        fail = int((df[lat] > r["latency_max_ms"]).sum())
        results.append({"rule": "Latency", "threshold": f"<= {r['latency_max_ms']} ms", "fail_rows": fail, "fail_pct": round(100 * fail / n, 2)})

    tp = _col(df, rf, "throughput", "throughput_mbps", "data throughput (mbps)")
    if tp and pd.api.types.is_numeric_dtype(df[tp]):
        fail = int((df[tp] < r["throughput_min_mbps"]).sum())
        results.append({"rule": "Throughput", "threshold": f">= {r['throughput_min_mbps']} Mbps", "fail_rows": fail, "fail_pct": round(100 * fail / n, 2)})

    loss = _col(df, rf, "packet_loss", "packet_loss_pct", "packet loss rate (%)")
    if loss and pd.api.types.is_numeric_dtype(df[loss]):
        fail = int((df[loss] > r["packet_loss_max_pct"]).sum())
        results.append({"rule": "Packet loss", "threshold": f"<= {r['packet_loss_max_pct']}%", "fail_rows": fail, "fail_pct": round(100 * fail / n, 2)})

    overall = "PASS" if not results or all(x["fail_pct"] < 5 for x in results) else "REVIEW"
    return {"ok": True, "rows": n, "overall": overall, "rules": results, "path": path}
