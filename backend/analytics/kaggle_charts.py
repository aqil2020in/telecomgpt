"""Auto-generate Plotly charts from local Kaggle CSV files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from .charts import chart_from_csv
from .csv_tools import csv_summary, detect_rf_columns, load_csv_path

_KAGGLE_DIR = Path(__file__).resolve().parent.parent / "data" / "kaggle"

_DATASET_HINTS: dict[str, tuple[str, ...]] = {
    "kpi": ("kpi", "5g-network-kpi", "dataset1_5g"),
    "slicing": ("slicing", "slice", "qos", "6g_network"),
    "cellular": ("cellular", "signal_metrics", "drive", "rsrp", "gps"),
}


def list_kaggle_csv_paths() -> list[Path]:
    if not _KAGGLE_DIR.exists():
        return []
    return sorted(p for p in _KAGGLE_DIR.rglob("*.csv") if p.is_file())


def pick_csv_path(query: str = "", explicit: str | None = None) -> Path | None:
    paths = list_kaggle_csv_paths()
    if not paths:
        return None
    if explicit:
        ep = Path(explicit)
        if ep.exists():
            return ep
        for p in paths:
            if explicit.lower() in str(p).lower():
                return p

    q = query.lower()
    for key, hints in _DATASET_HINTS.items():
        if any(h in q for h in hints):
            for p in paths:
                if any(h in p.name.lower() or h in str(p.parent).lower() for h in hints):
                    return p

    # Prefer KPI dataset, then slicing, then any with GPS, then first
    for prefer in ("dataset1_5g", "6G_network", "signal_metrics"):
        for p in paths:
            if prefer.lower() in p.name.lower():
                return p
    return paths[0]


def _sample_df(df: pd.DataFrame, max_rows: int | None = None) -> pd.DataFrame:
    from memory.runtime_config import kaggle_max_rows

    cap = max_rows if max_rows is not None else kaggle_max_rows()
    if len(df) <= cap:
        return df
    step = max(1, len(df) // cap)
    return df.iloc[::step].copy()


def _find_col(df: pd.DataFrame, *candidates: str) -> str | None:
    cols = {str(c).lower(): str(c) for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols:
            return cols[cand.lower()]
    for col in df.columns:
        cl = str(col).lower()
        for cand in candidates:
            if cand.lower() in cl:
                return str(col)
    return None


def _chart_specs(df: pd.DataFrame, rf: dict[str, str | None]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    numeric = [str(c) for c in df.select_dtypes(include="number").columns]

    time_col = _find_col(df, "timestamp", "time", "date")
    rsrp = rf.get("rsrp") or _find_col(df, "rsrp", "signal strength", "signal_strength")
    throughput = rf.get("throughput") or _find_col(
        df, "throughput", "throughput_mbps", "data throughput", "qos metric"
    )
    latency = _find_col(df, "latency", "latency_ms", "latency (ms)")
    slice_col = _find_col(df, "slice_type", "slice", "network slice", "network type")

    if time_col and throughput:
        specs.append({"chart_type": "line", "x": time_col, "y": throughput, "title": f"{throughput} over time"})
    if rsrp:
        specs.append({"chart_type": "histogram", "x": rsrp, "title": f"Distribution: {rsrp}"})
    if rsrp and throughput:
        specs.append({"chart_type": "scatter", "x": rsrp, "y": throughput, "title": f"{throughput} vs {rsrp}"})
    if latency:
        specs.append({"chart_type": "histogram", "x": latency, "title": f"Distribution: {latency}"})
    if slice_col:
        specs.append({"chart_type": "bar", "x": slice_col, "title": f"Counts by {slice_col}"})
    if not specs and len(numeric) >= 2:
        specs.append({"chart_type": "scatter", "x": numeric[0], "y": numeric[1], "title": f"{numeric[1]} vs {numeric[0]}"})
    elif not specs and numeric:
        specs.append({"chart_type": "histogram", "x": numeric[0], "title": f"Distribution: {numeric[0]}"})

    return specs[:4]


def build_kaggle_dashboard(
    query: str = "",
    *,
    csv_path: str | Path | None = None,
    max_rows: int = 2000,
) -> dict[str, Any]:
    path = Path(csv_path) if csv_path else pick_csv_path(query)
    if not path or not path.exists():
        return {"ok": False, "error": "No Kaggle CSV files found under backend/data/kaggle/"}

    df = load_csv_path(str(path))
    df = _sample_df(df, max_rows=max_rows)
    rf = detect_rf_columns(df)
    summary = csv_summary(df)
    charts: list[dict[str, Any]] = []

    for spec in _chart_specs(df, rf):
        try:
            plotly_json = chart_from_csv(
                df,
                chart_type=spec["chart_type"],
                x=spec.get("x"),
                y=spec.get("y"),
            )
            charts.append(
                {
                    "type": "chart",
                    "ok": True,
                    "title": spec["title"],
                    "chart_type": spec["chart_type"],
                    "plotly_json": plotly_json,
                    "source_csv": path.name,
                }
            )
        except Exception as e:
            charts.append({"type": "chart", "ok": False, "title": spec.get("title"), "error": str(e)})

    return {
        "ok": True,
        "dataset": path.name,
        "path": str(path),
        "summary": {
            "rows": summary.get("rows"),
            "columns": summary.get("columns"),
            "rf_columns": rf,
            "has_gps": summary.get("has_gps"),
            "numeric_columns": summary.get("numeric_columns", [])[:8],
        },
        "charts": charts,
    }
