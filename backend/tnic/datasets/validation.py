"""Dataset validation layer."""

from __future__ import annotations

import pandas as pd

from tnic.datasets.loaders import (
    load_call_drop_events,
    load_handover_events,
    load_pm_counters,
    load_rach_events,
    load_rlf_events,
    load_throughput_metrics,
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
    allowed = {"Core", "IMS", "Mobility", "Radio", "Transport", "None"}
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


def validate_dataset(name: str) -> DatasetValidationResult:
    validators = {
        "pm_counters": (load_pm_counters, _validate_pm_counters),
        "handover_events": (load_handover_events, _validate_handover),
        "rlf_events": (load_rlf_events, _validate_rlf),
        "rach_events": (load_rach_events, _validate_rach),
        "call_drop_events": (load_call_drop_events, _validate_call_drop),
        "throughput_metrics": (load_throughput_metrics, _validate_throughput),
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
    ]
    return [validate_dataset(n) for n in names]
