"""Pytest fixtures for XYZ TNIC."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("TNIC_ENABLE_CHROMA", "0")
os.environ.setdefault("OPENAI_API_KEY", "")


@pytest.fixture
def pm_csv_path() -> Path:
    return ROOT / "data" / "pm_counters.csv"


@pytest.fixture
def cell_kpis(pm_csv_path):
    from tnic.services.pm_ingestion import aggregate_cell_kpis
    return aggregate_cell_kpis(pm_csv_path)["43211"]


@pytest.fixture
def healthy_kpis():
    return {
        "ss_rsrp": -82.0,
        "ss_sinr": 18.0,
        "throughput_mbps": 145.0,
        "ho_success_rate": 97.5,
        "rach_success_rate": 98.0,
        "call_drop_rate": 0.5,
        "latency_ms": 25.0,
        "beam_failure_ratio": 8.0,
    }


@pytest.fixture
def degraded_kpis(cell_kpis):
    return cell_kpis
