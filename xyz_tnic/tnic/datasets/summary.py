"""Dataset summary service."""

from __future__ import annotations

from typing import Any

import pandas as pd

from tnic.datasets.loaders import load_all_dataframes
from tnic.datasets.models import DatasetSummary
from tnic.datasets.registry import DATASET_FILES, DatasetName, dataset_path, datasets_dir


def _numeric_stats(df: pd.DataFrame, cols: list[str]) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    for col in cols:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            stats[col] = {
                "min": float(df[col].min()),
                "max": float(df[col].max()),
                "mean": round(float(df[col].mean()), 2),
            }
    return stats


def summarize_pm_counters(df: pd.DataFrame) -> DatasetSummary:
    time_range = None
    if "timestamp" in df.columns:
        time_range = {
            "start": str(df["timestamp"].min()),
            "end": str(df["timestamp"].max()),
        }
    return DatasetSummary(
        name="pm_counters",
        file=DATASET_FILES[DatasetName.PM_COUNTERS],
        row_count=len(df),
        cell_count=df["cell_id"].nunique(),
        cells=sorted(df["cell_id"].unique().tolist()),
        columns=list(df.columns),
        time_range=time_range,
        numeric_stats=_numeric_stats(df, ["ho_attempt", "rach_attempt", "dl_tp", "cqi"]),
    )


def summarize_handover_events(df: pd.DataFrame) -> DatasetSummary:
    return DatasetSummary(
        name="handover_events",
        file=DATASET_FILES[DatasetName.HANDOVER_EVENTS],
        row_count=len(df),
        cell_count=df["cell_id"].nunique(),
        cells=sorted(df["cell_id"].unique().tolist()),
        columns=list(df.columns),
        category_counts=df["failure_type"].value_counts().to_dict(),
        numeric_stats=_numeric_stats(df, ["rsrp", "sinr"]),
    )


def summarize_rlf_events(df: pd.DataFrame) -> DatasetSummary:
    return DatasetSummary(
        name="rlf_events",
        file=DATASET_FILES[DatasetName.RLF_EVENTS],
        row_count=len(df),
        cell_count=df["cell_id"].nunique(),
        cells=sorted(df["cell_id"].unique().tolist()),
        columns=list(df.columns),
        category_counts=df["cause"].value_counts().to_dict(),
        numeric_stats=_numeric_stats(df, ["rsrp", "sinr"]),
    )


def summarize_rach_events(df: pd.DataFrame) -> DatasetSummary:
    return DatasetSummary(
        name="rach_events",
        file=DATASET_FILES[DatasetName.RACH_EVENTS],
        row_count=len(df),
        cell_count=df["cell_id"].nunique(),
        cells=sorted(df["cell_id"].unique().tolist()),
        columns=list(df.columns),
        category_counts=df["msg_failure"].value_counts().to_dict(),
    )


def summarize_call_drop_events(df: pd.DataFrame) -> DatasetSummary:
    return DatasetSummary(
        name="call_drop_events",
        file=DATASET_FILES[DatasetName.CALL_DROP_EVENTS],
        row_count=len(df),
        cell_count=df["cell_id"].nunique(),
        cells=sorted(df["cell_id"].unique().tolist()),
        columns=list(df.columns),
        category_counts=df["drop_type"].value_counts().to_dict(),
    )


def summarize_throughput_metrics(df: pd.DataFrame) -> DatasetSummary:
    return DatasetSummary(
        name="throughput_metrics",
        file=DATASET_FILES[DatasetName.THROUGHPUT_METRICS],
        row_count=len(df),
        cell_count=df["cell_id"].nunique(),
        cells=sorted(df["cell_id"].unique().tolist()),
        columns=list(df.columns),
        category_counts=df["issue"].value_counts().to_dict(),
        numeric_stats=_numeric_stats(df, ["cqi", "prb_util", "dl_tp"]),
    )


def summarize_dataset(name: str) -> DatasetSummary:
    frames = load_all_dataframes()
    if name not in frames:
        raise KeyError(f"Unknown dataset: {name}")
    df = frames[name]
    builders = {
        "pm_counters": summarize_pm_counters,
        "handover_events": summarize_handover_events,
        "rlf_events": summarize_rlf_events,
        "rach_events": summarize_rach_events,
        "call_drop_events": summarize_call_drop_events,
        "throughput_metrics": summarize_throughput_metrics,
    }
    return builders[name](df)


def summarize_all() -> dict[str, Any]:
    summaries = {name: summarize_dataset(name).model_dump() for name in load_all_dataframes()}
    return {
        "ok": True,
        "datasets_dir": str(datasets_dir()),
        "dataset_count": len(summaries),
        "summaries": summaries,
    }
