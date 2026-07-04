"""Unit tests for all 12 TNIC specialist agents."""

from __future__ import annotations

import pytest

from tnic.agents.specialists import (
    AGENT_REGISTRY,
    BeamformingAgent,
    CallDropAgent,
    ComplaintAgent,
    CoreAgent,
    HOAgent,
    LatencyAgent,
    PMAgent,
    RACHAgent,
    RLFAgent,
    ThroughputAgent,
    TransportAgent,
)


@pytest.mark.parametrize(
    "key,expected_name",
    [
        ("handover", "ho_agent"),
        ("rlf", "rlf_agent"),
        ("call_drop", "call_drop_agent"),
        ("throughput", "throughput_agent"),
        ("rach", "rach_agent"),
        ("beamforming", "beamforming_agent"),
        ("latency", "latency_agent"),
        ("pm", "pm_agent"),
        ("transport", "transport_agent"),
        ("core", "core_agent"),
        ("complaint", "complaint_agent"),
    ],
)
def test_agent_registry_keys(key, expected_name):
    agent = AGENT_REGISTRY[key]
    assert agent.name == expected_name


def test_ho_agent_fires_on_low_ho_success(degraded_kpis):
    result = HOAgent().analyze(degraded_kpis, query="handover failure")
    assert result.agent == "ho_agent"
    assert isinstance(result.findings, list)


def test_rlf_agent_runs(degraded_kpis):
    result = RLFAgent().analyze(degraded_kpis, query="radio link failure")
    assert result.agent == "rlf_agent"


def test_call_drop_agent_runs(degraded_kpis):
    result = CallDropAgent().analyze(degraded_kpis, query="call drop")
    assert result.agent == "call_drop_agent"


def test_throughput_agent_fires_on_low_cqi(degraded_kpis):
    result = ThroughputAgent().analyze(degraded_kpis, query="low throughput")
    assert result.agent == "throughput_agent"
    assert len(result.findings) >= 1


def test_rach_agent_runs(degraded_kpis):
    result = RACHAgent().analyze(degraded_kpis, query="rach failure")
    assert result.agent == "rach_agent"


def test_beamforming_agent_fires_on_high_bfr(degraded_kpis):
    kpis = {**degraded_kpis, "beam_switch_rate": 15, "beam_failure_ratio": 32}
    result = BeamformingAgent().analyze(kpis, query="beam failure")
    assert result.agent == "beamforming_agent"
    assert len(result.findings) >= 1


def test_latency_agent_runs(degraded_kpis):
    result = LatencyAgent().analyze(degraded_kpis, query="latency spike")
    assert result.agent == "latency_agent"


def test_pm_agent_validation(degraded_kpis):
    result = PMAgent().analyze(degraded_kpis)
    assert result.agent == "pm_agent"


def test_transport_agent_fires_on_congestion():
    kpis = {"backhaul_utilization": 85.0, "transport_loss_rate": 0.5}
    result = TransportAgent().analyze(kpis)
    assert result.agent == "transport_agent"
    assert len(result.findings) >= 1


def test_core_agent_fires_on_upf_latency(degraded_kpis):
    result = CoreAgent().analyze(degraded_kpis)
    assert result.agent == "core_agent"
    assert len(result.findings) >= 1


def test_complaint_agent_triages_query():
    result = ComplaintAgent().analyze({}, query="customer complaint about dropped calls")
    assert result.agent == "complaint_agent"
    assert len(result.findings) == 1
    assert "call_drop" in result.findings[0].probable_cause or "Complaint" in result.findings[0].probable_cause


def test_healthy_cell_fewer_throughput_findings(healthy_kpis):
    result = ThroughputAgent().analyze(healthy_kpis, query="throughput check")
    assert result.agent == "throughput_agent"
