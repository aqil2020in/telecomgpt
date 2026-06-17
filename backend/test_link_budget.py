"""Unit tests for link budget / SINR vs RSRQ. Run: python backend/test_link_budget.py"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analytics.link_budget import (
    compute_link_budget_scenario,
    explain_sinr_vs_rsrq_link_budget,
    friis_path_loss_db,
    looks_like_link_budget_query,
    rsrq_db,
    rssi_for_rsrq,
    sinr_db,
)
from telecom_ai.core import TelecomAI


def test_detection() -> None:
    assert looks_like_link_budget_query("Explain SINR vs RSRQ link budget")
    assert looks_like_link_budget_query("compare sinr and rsrq")
    assert looks_like_link_budget_query("Friis path loss n78")
    assert not looks_like_link_budget_query("What is band n78?")


def test_friis_and_kpis() -> None:
    fspl = friis_path_loss_db(1.0, 3500.0)
    assert 100 < fspl < 140
    rssi = rssi_for_rsrq(-85.0, -10.0, 50)
    rsrq = rsrq_db(-85.0, rssi, 50)
    assert abs(rsrq - (-10.0)) < 0.01
    s = sinr_db(-85.0, -95.0, -100.0)
    assert 5 < s < 15


def test_explanation_content() -> None:
    md = explain_sinr_vs_rsrq_link_budget("Explain SINR vs RSRQ link budget n78")
    for needle in (
        "SS-RSRP",
        "SS-RSRQ",
        "SS-SINR",
        "Worked DL link budget",
        "TS 38.215",
        "Friis",
        "Low interference",
    ):
        assert needle in md, f"missing {needle}"
    calc = compute_link_budget_scenario()
    assert calc["rsrp_dbm"] < -40
    assert len(calc["kpi_scenarios"]) == 2


def test_instant_answer_fast_path() -> None:
    ai = TelecomAI(str(Path(__file__).resolve().parent / "data" / "telecom_master_db.json"))
    out = ai.run_fast("Explain SINR vs RSRQ link budget")
    assert out.get("mode") == "fast-kb"
    assert "SS-RSRQ" in out["answer"]
    assert "Worked DL link budget" in out["answer"]


def test_api_endpoint() -> None:
    from fastapi.testclient import TestClient

    import app as app_module

    client = TestClient(app_module.app)
    r = client.get("/api/rf/link-budget", params={"q": "Explain SINR vs RSRQ link budget"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert "calculation" in data
    assert "SS-SINR" in data["markdown"]


def main() -> None:
    test_detection()
    test_friis_and_kpis()
    test_explanation_content()
    test_instant_answer_fast_path()
    test_api_endpoint()
    print("All link budget tests passed.")


if __name__ == "__main__":
    main()
