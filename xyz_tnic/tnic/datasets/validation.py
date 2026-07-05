"""Dataset validation layer."""

from __future__ import annotations

import pandas as pd

from tnic.datasets.loaders import (
    load_alarm_events,
    load_anr_events,
    load_call_drop_events,
    load_cell_configuration,
    load_gnb_syslog,
    load_handover_events,
    load_neighbor_relations,
    load_pm_counters,
    load_rach_events,
    load_rlf_events,
    load_throughput_metrics,
    load_vonr_sessions,
)
from tnic.datasets.models import DatasetValidationResult, ValidationIssue


def _validate_pm_counters(df: pd.DataFrame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for i, row in df.iterrows():
        if row.get("ho_success", 0) > row.get("ho_attempt", 0):
            issues.append(ValidationIssue(
                dataset="pm_counters", severity="error",
                message="ho_success exceeds ho_attempt", row=int(i),
            ))
        if row.get("rach_success", 0) > row.get("rach_attempt", 0):
            issues.append(ValidationIssue(
                dataset="pm_counters", severity="error",
                message="rach_success exceeds rach_attempt", row=int(i),
            ))
        cqi = row.get("cqi")
        if cqi is not None and (cqi < 0 or cqi > 15):
            issues.append(ValidationIssue(
                dataset="pm_counters", severity="error",
                message=f"CQI {cqi} out of range [0,15]", row=int(i),
            ))
    if df["cell_id"].isna().any():
        issues.append(ValidationIssue(
            dataset="pm_counters", severity="error", message="Missing cell_id values",
        ))
    if "timestamp" in df.columns:
        dup = df.duplicated(subset=["timestamp", "cell_id"]).sum()
        if dup:
            issues.append(ValidationIssue(
                dataset="pm_counters", severity="warning",
                message=f"{dup} duplicate (timestamp, cell_id) pairs",
            ))
    return issues


def _validate_events(df: pd.DataFrame, dataset: str, category_col: str, allowed: set[str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if df["cell_id"].isna().any():
        issues.append(ValidationIssue(dataset=dataset, severity="error", message="Missing cell_id values"))
    unknown = set(df[category_col].dropna().unique()) - allowed
    if unknown:
        issues.append(ValidationIssue(
            dataset=dataset, severity="warning",
            message=f"Unknown {category_col} values: {sorted(unknown)[:8]}",
        ))
    missing = df[category_col].isna().sum()
    if missing:
        issues.append(ValidationIssue(
            dataset=dataset, severity="warning",
            message=f"Missing {category_col} on {missing} rows",
        ))
    return issues


def _validate_handover(df: pd.DataFrame) -> list[ValidationIssue]:
    allowed = {
        "SUCCESS", "TOO_LATE_HO", "TOO_EARLY_HO", "PREP_FAILURE", "PING_PONG",
        "EXEC_FAILURE", "WRONG_CELL", "XN_FAILURE", "N2_FAILURE",
    }
    issues = _validate_events(df, "handover_events", "failure_type", allowed)
    for i, row in df.iterrows():
        if row.get("rsrp", -999) > 0:
            issues.append(ValidationIssue(
                dataset="handover_events", severity="warning",
                message="RSRP positive — expected dBm", row=int(i),
            ))
    return issues


def _validate_rlf(df: pd.DataFrame) -> list[ValidationIssue]:
    allowed = {"Coverage", "Post_HO", "Interference", "None"}
    return _validate_events(df, "rlf_events", "cause", allowed)


def _validate_rach(df: pd.DataFrame) -> list[ValidationIssue]:
    allowed = {"SUCCESS", "MSG1", "MSG2", "MSG3", "MSG4"}
    issues = _validate_events(df, "rach_events", "msg_failure", allowed)
    dup = df.duplicated().sum()
    if dup:
        issues.append(ValidationIssue(
            dataset="rach_events", severity="warning", message=f"{dup} duplicate rows",
        ))
    return issues


def _validate_call_drop(df: pd.DataFrame) -> list[ValidationIssue]:
    allowed = {"Core", "IMS", "Mobility", "Radio", "Transport"}
    return _validate_events(df, "call_drop_events", "drop_type", allowed)


def _validate_throughput(df: pd.DataFrame) -> list[ValidationIssue]:
    allowed = {"Congestion", "RF", "Scheduler", "Backhaul", "None"}
    issues = _validate_events(df, "throughput_metrics", "issue", allowed)
    for i, row in df.iterrows():
        if row.get("prb_util", 0) > 100:
            issues.append(ValidationIssue(
                dataset="throughput_metrics", severity="error",
                message="prb_util > 100", row=int(i),
            ))
    return issues


def _validate_alarm_events(df: pd.DataFrame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    allowed_sev = {"CRITICAL", "MAJOR", "MINOR", "WARNING", "INFO"}
    if df["cell_id"].isna().any():
        issues.append(ValidationIssue(dataset="alarm_events", severity="error", message="Missing cell_id"))
    unknown = set(df["severity"].dropna().unique()) - allowed_sev
    if unknown:
        issues.append(ValidationIssue(
            dataset="alarm_events", severity="warning",
            message=f"Unknown severity values: {sorted(unknown)}",
        ))
    return issues


def _validate_anr_events(df: pd.DataFrame) -> list[ValidationIssue]:
    allowed = {"PCI_CONFLICT", "MISSING_NEIGHBOR", "ANR_ADD_FAIL", "ANR_REMOVE", "STALE_NEIGHBOR"}
    return _validate_events(df, "anr_events", "event_type", allowed)


def _validate_neighbor_relations(df: pd.DataFrame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if "source_cell" not in df.columns or "target_cell" not in df.columns:
        issues.append(ValidationIssue(dataset="neighbor_relations", severity="error", message="Missing source/target columns"))
    allowed = {"ACTIVE", "MISSING", "BLACKLISTED", "STALE"}
    unknown = set(df.get("relation_status", pd.Series()).dropna().unique()) - allowed
    if unknown:
        issues.append(ValidationIssue(
            dataset="neighbor_relations", severity="warning",
            message=f"Unknown relation_status: {sorted(unknown)}",
        ))
    return issues


def _validate_vonr_sessions(df: pd.DataFrame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if df["cell_id"].isna().any():
        issues.append(ValidationIssue(dataset="vonr_sessions", severity="error", message="Missing cell_id"))
    allowed_result = {"SUCCESS", "DROP", "FAIL"}
    unknown = set(df["result"].dropna().unique()) - allowed_result
    if unknown:
        issues.append(ValidationIssue(
            dataset="vonr_sessions", severity="warning",
            message=f"Unknown result values: {sorted(unknown)}",
        ))
    return issues


def _validate_cell_configuration(df: pd.DataFrame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    required = {"cell_id", "pci", "a3_offset", "hysteresis", "time_to_trigger", "neighbor_count"}
    missing_cols = required - set(df.columns)
    if missing_cols:
        issues.append(ValidationIssue(
            dataset="cell_configuration", severity="error",
            message=f"Missing columns: {sorted(missing_cols)}",
        ))
    for i, row in df.iterrows():
        if row.get("neighbor_count", 0) < 0:
            issues.append(ValidationIssue(
                dataset="cell_configuration", severity="error",
                message="neighbor_count negative", row=int(i),
            ))
    return issues


def _validate_gnb_syslog(df: pd.DataFrame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if df["cell_id"].isna().any():
        issues.append(ValidationIssue(dataset="gnb_syslog", severity="error", message="Missing cell_id"))
    if "event_code" in df.columns and df["event_code"].isna().sum() > len(df) * 0.5:
        issues.append(ValidationIssue(
            dataset="gnb_syslog", severity="warning",
            message=">50% rows missing event_code",
        ))
    return issues


def validate_dataset(name: str) -> DatasetValidationResult:
    validators = {
        "pm_counters": (load_pm_counters, _validate_pm_counters),
        "handover_events": (load_handover_events, _validate_handover),
        "rlf_events": (load_rlf_events, _validate_rlf),
        "rach_events": (load_rach_events, _validate_rach),
        "call_drop_events": (load_call_drop_events, _validate_call_drop),
        "throughput_metrics": (load_throughput_metrics, _validate_throughput),
        "gnb_syslog": (load_gnb_syslog, _validate_gnb_syslog),
        "cell_configuration": (load_cell_configuration, _validate_cell_configuration),
        "neighbor_relations": (load_neighbor_relations, _validate_neighbor_relations),
        "anr_events": (load_anr_events, _validate_anr_events),
        "vonr_sessions": (load_vonr_sessions, _validate_vonr_sessions),
        "alarm_events": (load_alarm_events, _validate_alarm_events),
    }
    if name not in validators:
        return DatasetValidationResult(dataset=name, ok=False, row_count=0, issues=[
            ValidationIssue(dataset=name, severity="error", message=f"Unknown dataset: {name}"),
        ])
    loader, fn = validators[name]
    df = loader()
    issues = fn(df)
    errors = [x for x in issues if x.severity == "error"]
    return DatasetValidationResult(
        dataset=name,
        ok=len(errors) == 0,
        row_count=len(df),
        issues=issues,
    )


def validate_all() -> list[DatasetValidationResult]:
    names = [
        "pm_counters", "handover_events", "rlf_events",
        "rach_events", "call_drop_events", "throughput_metrics",
        "gnb_syslog", "cell_configuration", "neighbor_relations",
        "anr_events", "vonr_sessions", "alarm_events",
    ]
    results = []
    for n in names:
        try:
            results.append(validate_dataset(n))
        except FileNotFoundError:
            results.append(DatasetValidationResult(
                dataset=n, ok=False, row_count=0,
                issues=[ValidationIssue(dataset=n, severity="error", message="Dataset file not found")],
            ))
    return results
