"""Normalization engine — convert classified uploads into NormalizedEvent records."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from tnic.models.normalized_event import NormalizedEvent
from tnic.models.upload_models import FileClassification, SchemaInference
from tnic.services.file_classifier import classify_file
from tnic.services.gnb_syslog_parser import parse_syslog_text
from tnic.services.schema_inference import (
    extract_log_lines,
    extract_pcap_text_sample,
    infer_column_map,
    infer_schema_from_dataframe,
    infer_schema_from_log_lines,
    infer_schema_from_records,
    load_tabular,
)

FAIL_RESULTS = frozenset({"FAIL", "FAILURE", "DROP", "REJECT", "TIMEOUT", "CRITICAL", "MAJOR", "ERROR"})

DOMAIN_MAP = {
    "TELECOM_ISSUES": "telecom_issues",
    "UE_PROTOCOL_TRACE": "ue_protocol",
    "GNB_SYSLOG": "gnb_syslog",
    "ALARM": "alarm",
    "PM_COUNTERS": "pm",
    "RF_MEASUREMENT": "rf_coverage",
    "TRANSPORT": "transport",
    "NEIGHBOR": "anr",
    "CONFIGURATION": "config_audit",
    "VONR": "vonr",
    "UNKNOWN": "unknown",
}


def _get(row: dict[str, Any], col_map: dict[str, str], key: str, default: str = "") -> str:
    src = col_map.get(key)
    if src and src in row:
        val = row[src]
        return "" if val is None else str(val)
    return default


def _severity_from_result(result: str, default: str = "info") -> str:
    r = result.upper()
    if r in FAIL_RESULTS:
        return "fail"
    if r in ("SUCCESS", "OK", "PASS", "CLEARED"):
        return "info"
    return default


from tnic.datasets.telecom_issues import _norm_domain, _result_from_row


def _row_to_event(
    row: dict[str, Any],
    col_map: dict[str, str],
    *,
    source: str,
    domain: str,
    default_event: str = "",
) -> NormalizedEvent:
    result = _get(row, col_map, "result")
    severity_raw = _get(row, col_map, "severity", "")
    severity = severity_raw.lower() if severity_raw else _severity_from_result(result)
    event = (
        _get(row, col_map, "message")
        or _get(row, col_map, "alarm_name")
        or _get(row, col_map, "counter_name")
        or default_event
        or "EVENT"
    )
    meta = {k: v for k, v in row.items() if v not in ("", None)}
    if result:
        meta.setdefault("result", result)
    cause = _get(row, col_map, "cause")
    if cause:
        meta["cause"] = cause
    layer = _get(row, col_map, "layer")
    if layer:
        meta["layer"] = layer
    procedure = _get(row, col_map, "procedure")
    if procedure:
        meta["procedure"] = procedure
    for rf_key in ("rsrp", "sinr", "cqi"):
        val = _get(row, col_map, rf_key)
        if val:
            meta[rf_key] = val
    return NormalizedEvent(
        timestamp=_get(row, col_map, "timestamp"),
        cell_id=_get(row, col_map, "cell_id").upper(),
        ue_id=_get(row, col_map, "ue_id").upper(),
        source=source,
        domain=domain,
        event=event.upper(),
        severity=severity,
        metadata=meta,
    )


def _telecom_issues_row_to_event(
    row: dict[str, Any],
    col_map: dict[str, str],
    *,
    source: str,
) -> NormalizedEvent:
    issue_domain = _norm_domain(
        _get(row, col_map, "issue_domain")
        or row.get("issue_domain", "")
    )
    event_type = (
        _get(row, col_map, "event_type")
        or _get(row, col_map, "failure_type")
        or _get(row, col_map, "drop_type")
        or _get(row, col_map, "msg_failure")
        or "EVENT"
    )
    result = _result_from_row(_get(row, col_map, "result"), event_type, issue_domain)
    severity_raw = _get(row, col_map, "severity", "")
    severity = severity_raw.lower() if severity_raw else _severity_from_result(result)
    meta = {k: v for k, v in row.items() if v not in ("", None)}
    meta["issue_domain"] = issue_domain
    meta["event_type"] = event_type
    meta["result"] = result
    cause = _get(row, col_map, "cause")
    if cause:
        meta["cause"] = cause
    for key in ("rsrp", "sinr", "cqi", "target_cell", "source_cell", "dl_tp", "prb_util",
                "alarm_name", "module", "event_code", "message", "details",
                "beam_id", "beam_health_score", "beam_switch_rate"):
        val = _get(row, col_map, key) or row.get(key, "")
        if val:
            meta[key] = val
    return NormalizedEvent(
        timestamp=_get(row, col_map, "timestamp"),
        cell_id=_get(row, col_map, "cell_id").upper(),
        ue_id=_get(row, col_map, "ue_id").upper(),
        source=source,
        domain=issue_domain,
        event=str(event_type).upper(),
        severity=severity,
        metadata=meta,
    )


def normalize_dataframe(
    df: pd.DataFrame,
    classification: FileClassification,
    schema: SchemaInference,
    *,
    source: str,
) -> list[NormalizedEvent]:
    domain = DOMAIN_MAP.get(classification.file_type, "unknown")
    col_map = schema.column_map or infer_column_map(list(df.columns))
    events: list[NormalizedEvent] = []
    for rec in df.fillna("").astype(str).to_dict(orient="records"):
        if classification.file_type == "TELECOM_ISSUES":
            events.append(_telecom_issues_row_to_event(rec, col_map, source=source))
            continue
        ev = _row_to_event(rec, col_map, source=source, domain=domain)
        if classification.file_type == "PM_COUNTERS" and not ev.event:
            ev.event = _get(rec, col_map, "counter_name", "PM_COUNTER")
            ev.domain = "pm"
        if classification.file_type == "NEIGHBOR":
            src = _get(rec, col_map, "source_cell")
            tgt = _get(rec, col_map, "target_cell")
            ev.cell_id = src.upper() if src else ev.cell_id
            ev.event = f"NEIGHBOR_{tgt.upper()}" if tgt else "NEIGHBOR_RELATION"
            ev.metadata.setdefault("target_cell", tgt)
        events.append(ev)
    return events


def normalize_log_lines(
    lines: list[str],
    classification: FileClassification,
    *,
    source: str,
) -> list[NormalizedEvent]:
    domain = DOMAIN_MAP.get(classification.file_type, "unknown")
    events: list[NormalizedEvent] = []
    ts_re = re.compile(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})")
    cell_re = re.compile(r"\b(XYZ\d{3,4}|432\d{2})\b", re.I)
    ue_re = re.compile(r"\b(UE\d+)\b", re.I)

    if classification.file_type == "GNB_SYSLOG":
        parsed = parse_syslog_text("\n".join(lines))
        for p in parsed:
            events.append(NormalizedEvent(
                timestamp="",
                cell_id="",
                ue_id="",
                source=source,
                domain="gnb_syslog",
                event=p.get("rule_id", "SYSLOG_SIGNATURE"),
                severity="fail",
                metadata={
                    "probable_cause": p.get("probable_cause", ""),
                    "confidence": p.get("confidence"),
                    "evidence": p.get("evidence", {}),
                },
            ))
        if events:
            return events

    for line in lines:
        ts_m = ts_re.search(line)
        cell_m = cell_re.search(line)
        ue_m = ue_re.search(line)
        sev = "fail" if any(t in line.upper() for t in FAIL_RESULTS) else "info"
        if classification.file_type == "GNB_SYSLOG" and sev == "info":
            if not re.search(r"HO_PREP|T310|RLF|NGAP|MSG1|DRB|SIP", line, re.I):
                continue
            sev = "fail"
        events.append(NormalizedEvent(
            timestamp=ts_m.group(1) if ts_m else "",
            cell_id=cell_m.group(1).upper() if cell_m else "",
            ue_id=ue_m.group(1).upper() if ue_m else "",
            source=source,
            domain=domain,
            event=line[:120].upper(),
            severity=sev,
            metadata={"raw_line": line},
        ))
    return events


def normalize_uploaded_file(
    path: Path,
    classification: FileClassification | None = None,
) -> tuple[list[NormalizedEvent], FileClassification, SchemaInference]:
    """Full normalization pipeline for a single file."""
    source = path.name
    suffix = path.suffix.lower()

    if suffix == ".zip":
        return _normalize_zip(path, classification)

    if suffix in (".csv", ".xlsx", ".xls", ".json"):
        df = load_tabular(path)
        text_sample = df.head(20).astype(str).to_string()
        clf = classification or classify_file(path.name, columns=list(df.columns), text_sample=text_sample, df=df)
        schema = infer_schema_from_dataframe(df)
        events = normalize_dataframe(df, clf, schema, source=source)
        return events, clf, schema

    if suffix in (".txt", ".log"):
        lines = extract_log_lines(path)
        text_sample = "\n".join(lines[:100])
        clf = classification or classify_file(path.name, text_sample=text_sample)
        schema = infer_schema_from_log_lines(lines)
        events = normalize_log_lines(lines, clf, source=source)
        return events, clf, schema

    if suffix == ".pcap":
        text_sample = extract_pcap_text_sample(path)
        clf = classification or classify_file(path.name, text_sample=text_sample)
        lines = [ln for ln in text_sample.splitlines() if ln.strip()]
        schema = infer_schema_from_log_lines(lines)
        events = normalize_log_lines(lines, clf, source=source)
        return events, clf, schema

    # Fallback: try as text
    lines = extract_log_lines(path)
    clf = classification or classify_file(path.name, text_sample="\n".join(lines[:50]))
    schema = infer_schema_from_log_lines(lines)
    events = normalize_log_lines(lines, clf, source=source)
    return events, clf, schema


def _normalize_zip(
    path: Path,
    classification: FileClassification | None,
) -> tuple[list[NormalizedEvent], FileClassification, SchemaInference]:
    import zipfile
    import tempfile

    all_events: list[NormalizedEvent] = []
    combined_schema = SchemaInference(format="zip", columns=[], column_map={}, row_count=0)
    last_clf = classification or FileClassification(file_type="UNKNOWN", confidence=0.2, signals=["zip"])

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(path, "r") as zf:
            zf.extractall(tmp_path)
        for member in sorted(tmp_path.rglob("*")):
            if member.is_file() and member.suffix.lower() in (
                ".csv", ".xlsx", ".xls", ".json", ".txt", ".log", ".pcap",
            ):
                evs, clf, schema = normalize_uploaded_file(member, classification)
                all_events.extend(evs)
                last_clf = clf
                combined_schema.row_count += schema.row_count
                combined_schema.columns = list(set(combined_schema.columns + schema.columns))

    return all_events, last_clf, combined_schema


def summarize_events(events: list[NormalizedEvent]) -> dict[str, Any]:
    cells = sorted({e.cell_id for e in events if e.cell_id})
    ues = sorted({e.ue_id for e in events if e.ue_id})
    failures = [e for e in events if e.is_failure()]
    domains = sorted({e.domain for e in events if e.domain})
    return {
        "cell_ids": cells,
        "ue_ids": ues,
        "event_count": len(events),
        "failure_count": len(failures),
        "domains": domains,
        "failures_preview": [f.to_dict() for f in failures[:20]],
        "events_preview": [e.to_dict() for e in events[:20]],
    }
