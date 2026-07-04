"""Pandas loaders for telecom RCA datasets."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from tnic.datasets.models import (
    CallDropEventRow,
    HandoverEventRow,
    PMCounterRow,
    RachEventRow,
    RLFEventRow,
    ThroughputMetricRow,
)
from tnic.datasets.registry import DatasetName, dataset_path


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


def load_all_dataframes() -> dict[str, pd.DataFrame]:
    return {
        "pm_counters": load_pm_counters(),
        "handover_events": load_handover_events(),
        "rlf_events": load_rlf_events(),
        "rach_events": load_rach_events(),
        "call_drop_events": load_call_drop_events(),
        "throughput_metrics": load_throughput_metrics(),
    }


def rows_as_models(name: DatasetName, limit: int = 100) -> list:
    loaders = {
        DatasetName.PM_COUNTERS: (load_pm_counters, PMCounterRow),
        DatasetName.HANDOVER_EVENTS: (load_handover_events, HandoverEventRow),
        DatasetName.RLF_EVENTS: (load_rlf_events, RLFEventRow),
        DatasetName.RACH_EVENTS: (load_rach_events, RachEventRow),
        DatasetName.CALL_DROP_EVENTS: (load_call_drop_events, CallDropEventRow),
        DatasetName.THROUGHPUT_METRICS: (load_throughput_metrics, ThroughputMetricRow),
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
    load_rlf_events.cache_clear()
    load_rach_events.cache_clear()
    load_call_drop_events.cache_clear()
    load_throughput_metrics.cache_clear()
