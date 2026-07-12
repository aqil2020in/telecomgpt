"""Pandas loaders for telecom RCA datasets."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from tnic.datasets.models import (
    AlarmEventRow,
    AnrEventRow,
    CallDropEventRow,
    CellConfigurationRow,
    GnbSyslogRow,
    HandoverEventRow,
    NeighborRelationRow,
    PMCounterRow,
    RachEventRow,
    RLFEventRow,
    ThroughputMetricRow,
    UEProtocolTraceRow,
    VonrSessionRow,
)
from tnic.datasets.registry import DatasetName, dataset_path, datasets_dir, DATASET_FILES

__all__ = [
    "load_pm_counters",
    "load_handover_events",
    "load_handover_events_enriched",
    "load_rlf_events",
    "load_rach_events",
    "load_call_drop_events",
    "load_throughput_metrics",
    "load_gnb_syslog",
    "load_cell_configuration",
    "load_neighbor_relations",
    "load_anr_events",
    "load_vonr_sessions",
    "load_alarm_events",
    "load_ue_protocol_trace",
    "load_telecom_issues",
    "load_all_dataframes",
    "load_assurance_dataframes",
    "rows_as_models",
    "clear_loader_cache",
]


def _read_csv(name: DatasetName, path: Path | None = None) -> pd.DataFrame:
    p = path or dataset_path(name)
    df = pd.read_csv(p)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


@lru_cache(maxsize=1)
def load_pm_counters(path: str | None = None) -> pd.DataFrame:
    df = _read_csv(DatasetName.PM_COUNTERS, Path(path) if path else None)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


@lru_cache(maxsize=1)
def load_handover_events(path: str | None = None) -> pd.DataFrame:
    return _read_csv(DatasetName.HANDOVER_EVENTS, Path(path) if path else None)


@lru_cache(maxsize=1)
def load_handover_events_enriched(path: str | None = None) -> pd.DataFrame:
    """RCA-ready handover events with derived mobility/RF/transport columns."""
    if path:
        df = pd.read_csv(path)
        df.columns = [c.strip().lower() for c in df.columns]
        return df
    enriched_path = datasets_dir() / DATASET_FILES[DatasetName.HANDOVER_EVENTS_ENRICHED]
    if enriched_path.exists():
        df = pd.read_csv(enriched_path)
        df.columns = [c.strip().lower() for c in df.columns]
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    from tnic.datasets.handover_enrichment import enrich_handover_events

    return enrich_handover_events(load_handover_events())


@lru_cache(maxsize=1)
def load_rlf_events(path: str | None = None) -> pd.DataFrame:
    return _read_csv(DatasetName.RLF_EVENTS, Path(path) if path else None)


@lru_cache(maxsize=1)
def load_rach_events(path: str | None = None) -> pd.DataFrame:
    return _read_csv(DatasetName.RACH_EVENTS, Path(path) if path else None)


@lru_cache(maxsize=1)
def load_call_drop_events(path: str | None = None) -> pd.DataFrame:
    return _read_csv(DatasetName.CALL_DROP_EVENTS, Path(path) if path else None)


@lru_cache(maxsize=1)
def load_throughput_metrics(path: str | None = None) -> pd.DataFrame:
    return _read_csv(DatasetName.THROUGHPUT_METRICS, Path(path) if path else None)


@lru_cache(maxsize=1)
def load_gnb_syslog(path: str | None = None) -> pd.DataFrame:
    df = _read_csv(DatasetName.GNB_SYSLOG, Path(path) if path else None)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


@lru_cache(maxsize=1)
def load_cell_configuration(path: str | None = None) -> pd.DataFrame:
    return _read_csv(DatasetName.CELL_CONFIGURATION, Path(path) if path else None)


@lru_cache(maxsize=1)
def load_neighbor_relations(path: str | None = None) -> pd.DataFrame:
    return _read_csv(DatasetName.NEIGHBOR_RELATIONS, Path(path) if path else None)


@lru_cache(maxsize=1)
def load_anr_events(path: str | None = None) -> pd.DataFrame:
    df = _read_csv(DatasetName.ANR_EVENTS, Path(path) if path else None)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


@lru_cache(maxsize=1)
def load_vonr_sessions(path: str | None = None) -> pd.DataFrame:
    df = _read_csv(DatasetName.VONR_SESSIONS, Path(path) if path else None)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


@lru_cache(maxsize=1)
def load_alarm_events(path: str | None = None) -> pd.DataFrame:
    df = _read_csv(DatasetName.ALARM_EVENTS, Path(path) if path else None)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


@lru_cache(maxsize=1)
def load_ue_protocol_trace(path: str | None = None) -> pd.DataFrame:
    df = _read_csv(DatasetName.UE_PROTOCOL_TRACE, Path(path) if path else None)
    return df


@lru_cache(maxsize=1)
def load_telecom_issues(path: str | None = None) -> pd.DataFrame:
    """Unified telecom issues dataset (all RCA domains in one CSV)."""
    p = Path(path) if path else datasets_dir() / DATASET_FILES[DatasetName.TELECOM_ISSUES]
    if not p.exists():
        raise FileNotFoundError(f"Dataset not found: {p}")
    df = pd.read_csv(p)
    df.columns = [c.strip().lower() for c in df.columns]
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df


def load_all_dataframes() -> dict[str, pd.DataFrame]:
    out = {
        "pm_counters": load_pm_counters(),
        "handover_events": load_handover_events(),
        "rlf_events": load_rlf_events(),
        "rach_events": load_rach_events(),
        "call_drop_events": load_call_drop_events(),
        "throughput_metrics": load_throughput_metrics(),
        "gnb_syslog": load_gnb_syslog(),
        "cell_configuration": load_cell_configuration(),
        "neighbor_relations": load_neighbor_relations(),
        "anr_events": load_anr_events(),
        "vonr_sessions": load_vonr_sessions(),
        "alarm_events": load_alarm_events(),
        "ue_protocol_trace": load_ue_protocol_trace(),
    }
    try:
        out["telecom_issues"] = load_telecom_issues()
    except FileNotFoundError:
        pass
    return out


def load_assurance_dataframes() -> dict[str, pd.DataFrame]:
    """Load only core assurance datasets (may skip missing files)."""
    out: dict[str, pd.DataFrame] = {}
    loaders = {
        "gnb_syslog": load_gnb_syslog,
        "cell_configuration": load_cell_configuration,
        "neighbor_relations": load_neighbor_relations,
        "anr_events": load_anr_events,
        "vonr_sessions": load_vonr_sessions,
        "alarm_events": load_alarm_events,
        "ue_protocol_trace": load_ue_protocol_trace,
    }
    for name, fn in loaders.items():
        try:
            out[name] = fn()
        except FileNotFoundError:
            continue
    return out


def rows_as_models(name: DatasetName, limit: int = 100) -> list:
    loaders = {
        DatasetName.PM_COUNTERS: (load_pm_counters, PMCounterRow),
        DatasetName.HANDOVER_EVENTS: (load_handover_events, HandoverEventRow),
        DatasetName.RLF_EVENTS: (load_rlf_events, RLFEventRow),
        DatasetName.RACH_EVENTS: (load_rach_events, RachEventRow),
        DatasetName.CALL_DROP_EVENTS: (load_call_drop_events, CallDropEventRow),
        DatasetName.THROUGHPUT_METRICS: (load_throughput_metrics, ThroughputMetricRow),
        DatasetName.GNB_SYSLOG: (load_gnb_syslog, GnbSyslogRow),
        DatasetName.CELL_CONFIGURATION: (load_cell_configuration, CellConfigurationRow),
        DatasetName.NEIGHBOR_RELATIONS: (load_neighbor_relations, NeighborRelationRow),
        DatasetName.ANR_EVENTS: (load_anr_events, AnrEventRow),
        DatasetName.VONR_SESSIONS: (load_vonr_sessions, VonrSessionRow),
        DatasetName.ALARM_EVENTS: (load_alarm_events, AlarmEventRow),
        DatasetName.UE_PROTOCOL_TRACE: (load_ue_protocol_trace, UEProtocolTraceRow),
    }
    loader, model_cls = loaders[name]
    df = loader()
    out = []
    for rec in df.head(limit).to_dict(orient="records"):
        out.append(model_cls.model_validate(rec))
    return out


def clear_loader_cache() -> None:
    load_pm_counters.cache_clear()
    load_handover_events.cache_clear()
    load_handover_events_enriched.cache_clear()
    load_rlf_events.cache_clear()
    load_rach_events.cache_clear()
    load_call_drop_events.cache_clear()
    load_throughput_metrics.cache_clear()
    load_gnb_syslog.cache_clear()
    load_cell_configuration.cache_clear()
    load_neighbor_relations.cache_clear()
    load_anr_events.cache_clear()
    load_vonr_sessions.cache_clear()
    load_alarm_events.cache_clear()
    load_ue_protocol_trace.cache_clear()
    load_telecom_issues.cache_clear()
