"""RF KPI evaluation — Good / Fair / Poor vs 3GPP-referenced thresholds."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from .csv_tools import detect_rf_columns, load_csv_path

Grade = Literal["good", "fair", "poor", "unknown"]

_THRESH_PATH = Path(__file__).resolve().parent.parent / "data" / "rf_kpi_thresholds.json"


def load_kpi_thresholds() -> dict[str, Any]:
    if not _THRESH_PATH.exists():
        return {"kpis": {}}
    return json.loads(_THRESH_PATH.read_text(encoding="utf-8"))


def _in_band(value: float, band: dict) -> bool:
    lo = band.get("min")
    hi = band.get("max")
    if lo is not None and hi is not None:
        return lo <= value < hi
    if lo is not None:
        return value >= lo
    if hi is not None:
        return value < hi
    return False


def grade_value(kpi: dict, value: float) -> Grade:
    direction = kpi.get("direction", "higher_better")
    if direction == "lower_better":
        if _in_band(value, kpi.get("good", {})):
            return "good"
        if _in_band(value, kpi.get("fair", {})):
            return "fair"
        if _in_band(value, kpi.get("poor", {})):
            return "poor"
    else:
        if _in_band(value, kpi.get("good", {})):
            return "good"
        if _in_band(value, kpi.get("fair", {})):
            return "fair"
        if _in_band(value, kpi.get("poor", {})):
            return "poor"
    return "unknown"


def _resolve_column(rf: dict[str, str | None], column_keys: list[str]) -> str | None:
    for key in column_keys:
        col = rf.get(key)
        if col:
            return col
    return None


def evaluate_series(series: pd.Series, kpi: dict) -> dict[str, Any]:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return {"present": False}

    grades: dict[str, int] = {"good": 0, "fair": 0, "poor": 0, "unknown": 0}
    for v in numeric:
        grades[grade_value(kpi, float(v))] += 1

    n = len(numeric)
    pct = {k: round(100 * v / n, 2) for k, v in grades.items()}
    dominant = max(("good", "fair", "poor"), key=lambda g: grades[g])
    if grades[dominant] == 0:
        dominant = "unknown"

    return {
        "present": True,
        "count": n,
        "mean": round(float(numeric.mean()), 2),
        "min": round(float(numeric.min()), 2),
        "max": round(float(numeric.max()), 2),
        "p50": round(float(numeric.median()), 2),
        "grades": grades,
        "grade_pct": pct,
        "overall_grade": dominant,
        "spec": kpi.get("spec"),
        "unit": kpi.get("unit"),
        "label": kpi.get("label"),
        "full_name": kpi.get("full_name"),
    }


def evaluate_rf_kpis(path: str) -> dict[str, Any]:
    """Grade drive-test / KPI CSV columns against lab thresholds."""
    df = load_csv_path(path)
    rf = detect_rf_columns(df)
    catalog = load_kpi_thresholds().get("kpis", {})

    metrics: dict[str, Any] = {}
    for kpi_id, kpi in catalog.items():
        col = _resolve_column(rf, kpi.get("column_keys") or [kpi_id])
        if not col or col not in df.columns:
            metrics[kpi_id] = {
                "present": False,
                "label": kpi.get("label"),
                "spec": kpi.get("spec"),
            }
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        result = evaluate_series(df[col], kpi)
        result["column"] = col
        metrics[kpi_id] = result

    present = [m for m in metrics.values() if m.get("present")]
    poor_kpis = [m["label"] for m in present if m.get("overall_grade") == "poor"]
    fair_kpis = [m["label"] for m in present if m.get("overall_grade") == "fair"]

    if poor_kpis:
        overall = "POOR"
    elif fair_kpis:
        overall = "FAIR"
    elif present:
        overall = "GOOD"
    else:
        overall = "NO_RF_KPI_COLUMNS"

    return {
        "ok": True,
        "path": path,
        "rows": len(df),
        "overall": overall,
        "metrics": metrics,
        "rf_columns_detected": rf,
    }


def format_kpi_report(result: dict[str, Any]) -> str:
    lines = [
        f"**RF KPI assessment** — overall **{result.get('overall')}** ({result.get('rows', 0)} samples)",
        "",
        "| KPI | Column | Mean | Grade mix (G/F/P) | 3GPP |",
        "|-----|--------|------|-------------------|------|",
    ]
    for _kid, m in (result.get("metrics") or {}).items():
        if not m.get("present"):
            continue
        g = m.get("grades", {})
        mix = f"{g.get('good', 0)}/{g.get('fair', 0)}/{g.get('poor', 0)}"
        unit = f" {m.get('unit')}" if m.get("unit") else ""
        lines.append(
            f"| {m.get('label')} | `{m.get('column')}` | {m.get('mean')}{unit} | {mix} | {m.get('spec')} |"
        )
    if len(lines) == 4:
        lines.append("| — | — | — | No SS-RSRP/CQI/etc. columns detected | — |")
    return "\n".join(lines)
