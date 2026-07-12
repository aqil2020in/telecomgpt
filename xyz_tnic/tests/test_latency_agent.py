"""Tests for the 5G Latency RCA Agent."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("TNIC_DATASETS_DIR", "/workspace/datasets")


@pytest.fixture(autouse=True)
def _clear_loader_cache():
    from tnic.datasets.loaders import clear_loader_cache

    clear_loader_cache()
    yield
    clear_loader_cache()


@pytest.fixture
def agent():
    from tnic.agents.latency_agent import LatencyAgent

    return LatencyAgent()


def test_diagnose_schema(agent):
    from tnic.agents.latency_agent import diagnose_latency

    result = diagnose_latency(cell_id="XYZ401")
    assert set(result.keys()) >= {"issue_class", "root_cause", "confidence", "metrics"}
    metrics = result["metrics"]
    assert set(metrics.keys()) >= {
        "air_latency_ms",
        "transport_latency_ms",
        "upf_latency_ms",
        "internet_latency_ms",
    }


@pytest.mark.parametrize(
    "metrics,expected",
    [
        (
            {"air_latency_ms": 32, "transport_latency_ms": 8, "upf_latency_ms": 15, "internet_latency_ms": 40, "ss_sinr": 2},
            "RF_RETRANSMISSION",
        ),
        (
            {"air_latency_ms": 10, "transport_latency_ms": 28, "upf_latency_ms": 20, "internet_latency_ms": 55, "prb_utilization": 72},
            "BACKHAUL_CONGESTION",
        ),
        (
            {"air_latency_ms": 12, "transport_latency_ms": 10, "upf_latency_ms": 62, "internet_latency_ms": 80},
            "UPF_OVERLOAD",
        ),
        (
            {"air_latency_ms": 12, "transport_latency_ms": 22, "upf_latency_ms": 18, "internet_latency_ms": 85, "transport_drop_count": 6},
            "TRANSPORT_ISSUE",
        ),
    ],
)
def test_classify_latency_issue(metrics, expected):
    from tnic.agents.latency_agent import classify_latency_issue

    assert classify_latency_issue(metrics) == expected


def test_synthesize_latency_metrics_shape(agent):
    from tnic.agents.latency_agent import synthesize_latency_metrics

    lat = synthesize_latency_metrics("XYZ401")
    assert lat["cell_id"] == "XYZ401"
    for key in ("air_latency_ms", "transport_latency_ms", "upf_latency_ms", "internet_latency_ms"):
        assert lat[key] > 0


def test_analyze_xyz401_detects_latency_issue(agent):
    result = agent.analyze(cell_id="XYZ401")
    assert result.issue_class in {
        "Backhaul Congestion",
        "UPF Overload",
        "Transport Issue",
        "RF Retransmission",
    }
    assert result.confidence >= 0.5


@pytest.mark.parametrize(
    "query,expected_label",
    [
        ("upf overload latency XYZ401", "UPF Overload"),
        ("backhaul congestion", "Backhaul Congestion"),
        ("transport issue packet loss", "Transport Issue"),
        ("harq air interface latency", "RF Retransmission"),
    ],
)
def test_query_hints(agent, query, expected_label):
    result = agent.analyze(cell_id="XYZ401", query=query)
    assert result.issue_class == expected_label


def test_explicit_metrics_upf_overload(agent):
    metrics = {
        "cell_id": "T1",
        "air_latency_ms": 10,
        "transport_latency_ms": 8,
        "upf_latency_ms": 68,
        "internet_latency_ms": 75,
    }
    result = agent.analyze(cell_id="T1", metrics=metrics)
    assert result.issue_class == "UPF Overload"


def test_specialist_wrapper_with_cell_id():
    from tnic.agents.specialists import LatencyAgent

    result = LatencyAgent().analyze({"cell_id": "XYZ401"}, query="latency spike")
    assert result.agent == "latency_agent"
    assert len(result.findings) == 1
    assert result.findings[0].category == "latency"


def test_specialist_wrapper_falls_back_to_rules(degraded_kpis):
    from tnic.agents.specialists import LatencyAgent

    kpis = {**degraded_kpis, "upf_latency_ms": 62, "air_latency_ms": 28}
    result = LatencyAgent().analyze(kpis, query="latency spike")
    assert result.agent == "latency_agent"
    assert len(result.findings) >= 1


def test_no_data_when_empty_scope(agent):
    result = agent.analyze()
    assert result.issue_class == "No Data"
    assert result.confidence == 0.0


def test_bad_cells_have_higher_air_latency_than_good(agent):
    from tnic.agents.latency_agent import synthesize_latency_metrics

    bad = synthesize_latency_metrics("XYZ401")
    good = synthesize_latency_metrics("XYZ410")
    assert bad["air_latency_ms"] > good["air_latency_ms"]
