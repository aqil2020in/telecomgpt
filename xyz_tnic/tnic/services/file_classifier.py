"""File classification engine — infer telecom dataset type from filename, schema, and patterns."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from tnic.models.upload_models import FileClassification

# Canonical file types (10 categories)
FILE_TYPES = (
    "TELECOM_ISSUES",
    "UE_PROTOCOL_TRACE",
    "GNB_SYSLOG",
    "ALARM",
    "PM_COUNTERS",
    "RF_MEASUREMENT",
    "TRANSPORT",
    "NEIGHBOR",
    "CONFIGURATION",
    "VONR",
    "UNKNOWN",
)

_FILENAME_HINTS: dict[str, tuple[str, ...]] = {
    "TELECOM_ISSUES": ("telecom_issues", "telecom-issues", "unified_issues", "all_issues", "rca_issues"),
    "UE_PROTOCOL_TRACE": ("ue_trace", "ue_protocol", "ue_log", "protocol_trace", "ue-log"),
    "GNB_SYSLOG": ("syslog", "gnb_log", "du_log", "cu_log", "gnb-syslog"),
    "ALARM": ("alarm", "fm_alarm", "fault", "alarms"),
    "PM_COUNTERS": ("pm_counter", "pm_", "kpi", "counter", "performance"),
    "RF_MEASUREMENT": ("rf_", "drive_test", "rsrp", "measurement", "geospatial", "coverage"),
    "TRANSPORT": ("transport", "backhaul", "n3", "n6", "fronthaul", "sctp"),
    "NEIGHBOR": ("neighbor", "nbr", "anr", "relation", "ncr"),
    "CONFIGURATION": ("config", "cell_config", "parameter", "cm_", "golden"),
    "VONR": ("vonr", "volte", "ims", "voice", "sip", "5qi"),
}

_COLUMN_HINTS: dict[str, tuple[str, ...]] = {
    "TELECOM_ISSUES": ("issue_domain", "event_type", "telecom_domain"),
    "UE_PROTOCOL_TRACE": (
        "ue_id", "layer", "procedure", "message", "msg1", "msg2", "msg3", "msg4",
        "rrc", "t310", "n310", "sib1", "mib", "pbch",
    ),
    "GNB_SYSLOG": ("event_code", "module", "severity", "syslog", "log_message"),
    "ALARM": ("alarm_name", "alarm_id", "alarm_type", "perceived_severity", "probable_cause"),
    "PM_COUNTERS": ("counter_name", "counter_value", "period_start", "kpi_name"),
    "RF_MEASUREMENT": ("rsrp", "rsrq", "sinr", "cqi", "latitude", "longitude", "beam_id"),
    "TRANSPORT": ("link_id", "packet_loss", "latency_ms", "jitter", "throughput_mbps", "interface"),
    "NEIGHBOR": ("source_cell", "target_cell", "neighbor_pci", "relation_status", "xn_status"),
    "CONFIGURATION": ("parameter", "current_value", "golden_value", "pci", "earfcn", "nr_arfcn"),
    "VONR": ("call_id", "mos", "5qi", "qfi", "rtp_loss", "jitter_ms", "codec"),
}

_LOG_PATTERNS: dict[str, tuple[str, ...]] = {
    "UE_PROTOCOL_TRACE": (
        r"\bMSG[1-4]\b", r"\bRRC\b", r"\bT310\b", r"\bSIB1\b", r"\bMIB\b",
        r"\bREGISTRATION\b", r"\bAUTHENTICATION\b",
    ),
    "GNB_SYSLOG": (
        r"HO_PREP_FAIL", r"T310_EXPIR", r"DRB_SETUP_FAIL", r"NGAP", r"XnAP",
        r"MSG1_FAIL", r"RLF", r"PRACH",
    ),
    "ALARM": (r"\bCRITICAL\b", r"\bMAJOR\b", r"\bALARM\b", r"FM_ALARM", r"faultId"),
    "TRANSPORT": (r"packet.?loss", r"backhaul", r"SCTP", r"link.?down", r"N3", r"N6"),
    "VONR": (r"VoNR", r"SIP", r"IMS", r"5QI.?1", r"RTP", r"mute"),
}


def _norm_cols(columns: list[str]) -> set[str]:
    return {c.strip().lower().replace("-", "_").replace(" ", "_") for c in columns}


def _score_filename(name: str) -> dict[str, float]:
    stem = Path(name).stem.lower()
    scores: dict[str, float] = {t: 0.0 for t in FILE_TYPES}
    for ftype, hints in _FILENAME_HINTS.items():
        for h in hints:
            if h in stem:
                scores[ftype] += 0.35
    return scores


def _score_columns(columns: list[str]) -> dict[str, float]:
    cols = _norm_cols(columns)
    scores: dict[str, float] = {t: 0.0 for t in FILE_TYPES}
    for ftype, hints in _COLUMN_HINTS.items():
        hits = sum(1 for h in hints if h in cols or any(h in c for c in cols))
        if hits:
            scores[ftype] += min(0.15 * hits, 0.75)
    # Strong signals
    if {"ue_id", "layer", "procedure"} <= cols or {"ue_id", "message", "result"} <= cols:
        scores["UE_PROTOCOL_TRACE"] += 0.5
    if "issue_domain" in cols and ("event_type" in cols or "failure_type" in cols):
        scores["TELECOM_ISSUES"] += 0.85
    if "issue_domain" in cols:
        scores["TELECOM_ISSUES"] += 0.35
    if "event_code" in cols and ("module" in cols or "message" in cols):
        scores["GNB_SYSLOG"] += 0.45
    if "counter_name" in cols or ("counter" in cols and "value" in cols):
        scores["PM_COUNTERS"] += 0.45
    if any(c in cols for c in ("rsrp", "ss_rsrp", "sinr", "ss_sinr")):
        scores["RF_MEASUREMENT"] += 0.45
    if "source_cell" in cols and ("target_cell" in cols or "neighbor_pci" in cols):
        scores["NEIGHBOR"] += 0.45
    if "alarm_name" in cols or "perceived_severity" in cols:
        scores["ALARM"] += 0.45
    return scores


def _score_log_text(text: str) -> dict[str, float]:
    scores: dict[str, float] = {t: 0.0 for t in FILE_TYPES}
    sample = text[:50000]
    for ftype, patterns in _LOG_PATTERNS.items():
        hits = sum(1 for p in patterns if re.search(p, sample, re.I))
        if hits:
            scores[ftype] += min(0.12 * hits, 0.72)
    return scores


def classify_file(
    filename: str,
    *,
    columns: list[str] | None = None,
    text_sample: str = "",
    df: pd.DataFrame | None = None,
) -> FileClassification:
    """Classify uploaded telecom file into one of 10 dataset types."""
    scores: dict[str, float] = {t: 0.0 for t in FILE_TYPES}
    signals: list[str] = []

    fn_scores = _score_filename(filename)
    for k, v in fn_scores.items():
        scores[k] += v
    if max(fn_scores.values()) > 0:
        signals.append(f"filename:{Path(filename).stem}")

    cols = list(columns or [])
    if df is not None and not cols:
        cols = list(df.columns)
    if cols:
        col_scores = _score_columns(cols)
        for k, v in col_scores.items():
            scores[k] += v
        top_col_hits = [c for c in _norm_cols(cols) if any(
            h in c for hints in _COLUMN_HINTS.values() for h in hints
        )][:6]
        if top_col_hits:
            signals.append(f"columns:{','.join(top_col_hits[:4])}")

    if text_sample:
        log_scores = _score_log_text(text_sample)
        for k, v in log_scores.items():
            scores[k] += v
        if max(log_scores.values()) > 0:
            signals.append("log_patterns")

    best = max(scores, key=lambda k: scores[k])
    confidence = min(0.98, round(scores[best], 2))
    if confidence < 0.25:
        best = "UNKNOWN"
        confidence = 0.2

    protocol_hints = _protocol_hints(best, cols, text_sample)
    return FileClassification(
        file_type=best,
        confidence=confidence,
        signals=signals,
        protocol_hints=protocol_hints,
    )


def _protocol_hints(file_type: str, columns: list[str], text: str) -> list[str]:
    hints: list[str] = []
    cols = _norm_cols(columns)
    if file_type == "UE_PROTOCOL_TRACE":
        for token in ("RRC", "RACH", "NAS", "MSG1", "T310", "SIB1", "5GSM", "IMS"):
            if token.lower() in cols or token.lower() in text.lower():
                hints.append(token)
    elif file_type == "GNB_SYSLOG":
        for token in ("HO_PREP_FAIL", "T310", "RLF", "NGAP", "DRB"):
            if token.lower() in text.lower():
                hints.append(token)
    elif file_type == "RF_MEASUREMENT":
        for token in ("RSRP", "SINR", "CQI"):
            if token.lower() in cols or token.lower() in text.lower():
                hints.append(token)
    return hints[:8]
