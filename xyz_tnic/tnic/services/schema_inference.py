"""Schema inference — detect columns and map to normalized event fields."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from tnic.models.upload_models import SchemaInference

# Canonical field aliases
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "timestamp": ("timestamp", "time", "datetime", "date_time", "event_time", "period_start"),
    "cell_id": ("cell_id", "cell", "cgi", "nci", "gnodeb_cell", "serving_cell"),
    "ue_id": ("ue_id", "ue", "imsi", "subscriber", "crnti"),
    "layer": ("layer", "protocol_layer", "stack"),
    "procedure": ("procedure", "proc", "procedure_name"),
    "message": ("message", "msg", "event", "event_name", "event_code"),
    "result": ("result", "status", "outcome"),
    "cause": ("cause", "failure_cause", "reason", "reject_cause"),
    "severity": ("severity", "level", "alarm_severity", "perceived_severity"),
    "module": ("module", "component", "source_module"),
    "rsrp": ("rsrp", "ss_rsrp", "ssb_rsrp", "avg_rsrp"),
    "sinr": ("sinr", "ss_sinr", "ssb_sinr", "avg_sinr"),
    "cqi": ("cqi", "avg_cqi", "wideband_cqi"),
    "counter_name": ("counter_name", "counter", "kpi_name", "metric_name"),
    "counter_value": ("counter_value", "value", "kpi_value", "metric_value"),
    "alarm_name": ("alarm_name", "alarm", "alarm_type", "fault_name"),
    "issue_domain": ("issue_domain", "telecom_domain", "domain", "issue_type", "rca_domain"),
    "event_type": ("event_type", "failure_type", "drop_type", "msg_failure", "issue", "event_subtype"),
    "failure_type": ("failure_type", "ho_failure", "ho_result"),
    "drop_type": ("drop_type", "drop_reason"),
    "msg_failure": ("msg_failure", "rach_failure"),
    "source_cell": ("source_cell", "serving_cell", "src_cell"),
    "target_cell": ("target_cell", "neighbor_cell", "tgt_cell"),
}


def _norm(name: str) -> str:
    return name.strip().lower().replace("-", "_").replace(" ", "_")


def infer_column_map(columns: list[str]) -> dict[str, str]:
    """Map source columns to canonical field names."""
    col_map: dict[str, str] = {}
    normalized = {_norm(c): c for c in columns}
    for canonical, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                col_map[canonical] = normalized[alias]
                break
    return col_map


def infer_schema_from_dataframe(df: pd.DataFrame, *, limit: int = 5) -> SchemaInference:
    cols = [str(c) for c in df.columns]
    col_map = infer_column_map(cols)
    sample = df.head(limit).fillna("").astype(str).to_dict(orient="records")
    return SchemaInference(
        format="tabular",
        columns=cols,
        column_map=col_map,
        row_count=len(df),
        sample_rows=sample,
    )


def infer_schema_from_records(records: list[dict[str, Any]], *, limit: int = 5) -> SchemaInference:
    if not records:
        return SchemaInference(format="json", columns=[], column_map={}, row_count=0)
    cols = list(records[0].keys())
    col_map = infer_column_map(cols)
    return SchemaInference(
        format="json",
        columns=cols,
        column_map=col_map,
        row_count=len(records),
        sample_rows=records[:limit],
    )


def infer_schema_from_log_lines(lines: list[str], *, limit: int = 5) -> SchemaInference:
    return SchemaInference(
        format="log",
        columns=["raw_line"],
        column_map={"message": "raw_line"},
        row_count=len(lines),
        sample_rows=[{"raw_line": ln} for ln in lines[:limit]],
    )


def load_tabular(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in (".xlsx", ".xls"):
        try:
            return pd.read_excel(path)
        except ImportError as e:
            raise ImportError("XLSX support requires openpyxl: pip install openpyxl") from e
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        if isinstance(data, list):
            return pd.DataFrame(data)
        if isinstance(data, dict) and "events" in data:
            return pd.DataFrame(data["events"])
        if isinstance(data, dict) and "records" in data:
            return pd.DataFrame(data["records"])
        return pd.DataFrame([data])
    raise ValueError(f"Unsupported tabular format: {suffix}")


def extract_log_lines(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def extract_pcap_text_sample(path: Path, max_bytes: int = 500_000) -> str:
    """Best-effort ASCII extraction from PCAP for pattern classification."""
    raw = path.read_bytes()[:max_bytes]
    ascii_runs = re.findall(rb"[\x20-\x7e]{8,}", raw)
    return "\n".join(r.decode("ascii", errors="ignore") for r in ascii_runs[:2000])
