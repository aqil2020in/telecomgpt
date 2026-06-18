"""Tests for RRC HARQ fault analysis. Run: python backend/test_harq_rrc_fault.py"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analytics.harq_rrc_fault import (
    explain_rrc_harq_fault,
    looks_like_rrc_harq_fault_query,
    scan_log_for_harq_rrc_faults,
)
from telecom_ai.core import TelecomAI


SAMPLE_LOG = """
PRACH sequence_index=0 ta=6
RAR rapid=0
PUSCH harq=0 rv_idx=0 crc=OK
RRC setup request
PDCCH dci=1_0 harq_feedback_timing=3
PDSCH harq=0 k1=4 rv_idx=0 crc=NOK retx=1
PRACH again
"""


def test_detection() -> None:
    assert looks_like_rrc_harq_fault_query("Fault analysis RRC fail")
    assert looks_like_rrc_harq_fault_query("rrc setup failure troubleshooting")
    assert not looks_like_rrc_harq_fault_query("What is band n78?")


def test_explanation_sections() -> None:
    md = explain_rrc_harq_fault("Fault analysis RRC fail")
    for section in (
        "K1 configuration",
        "Redundancy version",
        "HARQ processor",
        "Hybrid nature of HARQ",
        "Frame structure",
        "Practical examples",
        "Decision tree",
    ):
        assert section in md, f"missing section: {section}"


def test_log_scan() -> None:
    scan = scan_log_for_harq_rrc_faults(SAMPLE_LOG)
    assert scan.get("pattern_hits")
    assert any("rv" in k or "k1" in k for k in scan["pattern_hits"])
    md = explain_rrc_harq_fault("rrc fail", log_text=SAMPLE_LOG)
    assert "Log scan" in md


def test_instant_fast_path() -> None:
    ai = TelecomAI(str(Path(__file__).resolve().parent / "data" / "telecom_master_db.json"))
    out = ai.run_fast("Fault analysis RRC fail")
    assert out.get("mode") == "fast-kb"
    assert "K1 configuration" in out["answer"]


def test_api() -> None:
    from fastapi.testclient import TestClient

    import app as app_module

    client = TestClient(app_module.app)
    r = client.get("/api/fault/rrc-harq", params={"q": "Fault analysis RRC fail"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert "K1 configuration" in data["markdown"]


def main() -> None:
    test_detection()
    test_explanation_sections()
    test_log_scan()
    test_instant_fast_path()
    test_api()
    print("All HARQ RRC fault tests passed.")


if __name__ == "__main__":
    main()
