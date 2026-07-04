"""Tests for telecom dashboard data helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("TNIC_DATASETS_DIR", "/workspace/datasets")

from dashboard.dashboard_utils import (  # noqa: E402
    dataset_cells,
    executive_summary_df,
    handover_df,
    run_agent,
    synthesize_beam_metrics,
    worst_cells,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    from tnic.datasets.loaders import clear_loader_cache

    clear_loader_cache()
    yield
    clear_loader_cache()


def test_dataset_cells_include_demo_range():
    cells = dataset_cells()
    assert "XYZ401" in cells
    assert "XYZ410" in cells


def test_executive_summary_shape():
    df = executive_summary_df()
    assert len(df) >= 10
    assert "health_score" in df.columns
    assert "ho_success_rate" in df.columns


def test_handover_df_filtered():
    df = handover_df("XYZ401")
    assert (df["cell_id"] == "XYZ401").all()
    assert len(df) > 0


def test_synthesize_beam_metrics():
    beams = synthesize_beam_metrics("XYZ401")
    assert len(beams) == 8
    assert beams["beam_utilization"].max() > 0


def test_run_agent_handover():
    result = run_agent("handover", "XYZ401")
    assert result["agent"] == "ho_agent"
    assert isinstance(result["findings"], list)


def test_worst_cells():
    worst = worst_cells(3)
    assert len(worst) == 3
