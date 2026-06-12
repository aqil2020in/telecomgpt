"""Dataset schema registry — readiness checks for Test Engineer agents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .csv_tools import detect_rf_columns, load_csv_path

_DATA = Path(__file__).resolve().parent.parent / "data"
_SCHEMA_PATH = _DATA / "dataset_schemas.json"
_UPLOADS = _DATA / "uploads"
_KAGGLE = _DATA / "kaggle"


def load_schemas() -> dict[str, Any]:
    if not _SCHEMA_PATH.exists():
        return {"schemas": {}}
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _col_match(df: pd.DataFrame, names: list[str]) -> bool:
    cols = {str(c).lower() for c in df.columns}
    for name in names:
        if name.lower() in cols:
            return True
    rf = detect_rf_columns(df)
    for name in names:
        key = name.lower().replace(" ", "_").replace("-", "_")
        for rk, rv in rf.items():
            if rv and (name.lower() in rv.lower() or rk in key):
                return True
    return False


def classify_csv(df: pd.DataFrame) -> list[str]:
    matched: list[str] = []
    for sid, schema in load_schemas().get("schemas", {}).items():
        if not sid.endswith("_rf") and sid != "network_kpi":
            continue
        groups = schema.get("required_columns_any") or []
        if not groups:
            continue
        if all(_col_match(df, group) for group in groups):
            matched.append(sid)
    if not matched and _col_match(df, ["Signal Strength (dBm)", "rsrp", "SS-RSRP"]):
        matched.append("network_kpi")
    if not matched and detect_rf_columns(df).get("rsrp"):
        matched.append("network_kpi")
    return matched


def _session_uploads(session_id: str) -> list[Path]:
    base = _UPLOADS / session_id
    if not base.exists():
        return []
    return sorted(base.glob("*"))


def dataset_readiness(*, session_id: str = "default") -> dict[str, Any]:
    schemas = load_schemas().get("schemas", {})
    uploads = _session_uploads(session_id)
    kaggle_csvs = sorted(_KAGGLE.rglob("*.csv")) if _KAGGLE.exists() else []

    by_agent: dict[str, dict] = {}
    for sid, schema in schemas.items():
        agent = schema.get("agent", sid)
        by_agent.setdefault(agent, {"agent": agent, "schemas": [], "ready": False, "files": []})

    csv_paths = [p for p in uploads if p.suffix.lower() == ".csv"] + list(kaggle_csvs)[:5]
    log_paths = [p for p in uploads if p.suffix.lower() in (".log", ".txt")]
    config_paths = [p for p in uploads if p.suffix.lower() in (".json", ".xml")]

    for path in csv_paths:
        try:
            df = load_csv_path(str(path))
            kinds = classify_csv(df)
            for kind in kinds:
                schema = schemas.get(kind, {})
                agent = schema.get("agent", kind)
                entry = by_agent.setdefault(agent, {"agent": agent, "schemas": [], "ready": False, "files": []})
                entry["ready"] = True
                if kind not in entry["schemas"]:
                    entry["schemas"].append(kind)
                entry["files"].append({"path": str(path), "rows": len(df), "schema": kind})
        except Exception:
            continue

    if log_paths:
        entry = by_agent.setdefault("log_debug", {"agent": "log_debug", "schemas": [], "ready": False, "files": []})
        entry["ready"] = True
        entry["schemas"].append("qxdm_log")
        for p in log_paths:
            entry["files"].append({"path": str(p), "schema": "qxdm_log"})

    if config_paths:
        entry = by_agent.setdefault("bts_config", {"agent": "bts_config", "schemas": [], "ready": False, "files": []})
        entry["ready"] = True
        entry["schemas"].append("bts_config")
        for p in config_paths:
            entry["files"].append({"path": str(p), "schema": "bts_config"})

    # Agents with built-in templates work without uploads
    by_agent.setdefault(
        "feature_validation",
        {"agent": "feature_validation", "schemas": ["feature_test_plan"], "ready": True, "files": [], "builtin": True},
    )
    by_agent.setdefault(
        "fault_analysis",
        {"agent": "fault_analysis", "schemas": ["fault_catalog"], "ready": True, "files": [], "builtin": True},
    )
    by_agent.setdefault(
        "spec",
        {"agent": "spec", "schemas": ["3gpp_rag"], "ready": True, "files": [], "builtin": True},
    )

    missing = [
        {"schema": sid, "label": s.get("label"), "agent": s.get("agent"), "notes": s.get("notes")}
        for sid, s in schemas.items()
        if not by_agent.get(s.get("agent", sid), {}).get("ready")
        and s.get("agent") not in ("feature_validation", "fault_analysis")
    ]

    return {
        "session_id": session_id,
        "agents": list(by_agent.values()),
        "missing_datasets": missing,
        "upload_hint": "Upload CSV/logs/config to data/uploads/{session_id} via POST /api/upload",
    }
