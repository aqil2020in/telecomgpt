"""Health score engine tests."""

from __future__ import annotations

from tnic.services.health_scoring import cell_health_response, compute_health_score


def test_healthy_cell_scores_high(healthy_kpis):
    score = compute_health_score(healthy_kpis)
    assert score["overall_score"] >= 85
    assert score["grade"] in ("A", "B")


def test_degraded_cell_scores_lower(degraded_kpis):
    score = compute_health_score(degraded_kpis)
    assert score["overall_score"] < 75
    assert score["grade"] in ("C", "D", "B")


def test_cell_health_response_includes_cell_id(degraded_kpis):
    resp = cell_health_response("43211", degraded_kpis)
    assert resp["cell_id"] == "43211"
    assert "dimensions" in resp
    assert "alerts" in resp
