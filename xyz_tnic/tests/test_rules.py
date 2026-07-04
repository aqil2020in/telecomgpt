"""Rule engine tests."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["APP_ENV"] = "test"

from app.rules.ho_rules import HO_RULE_ENGINE
from app.rules.throughput_rules import THROUGHPUT_RULE_ENGINE
from app.rules.call_drop_rules import CALL_DROP_RULE_ENGINE
from app.rules import detect_issue_type


def test_ho_prep_failure():
    findings = HO_RULE_ENGINE.evaluate({"ho_prep_fail_rate": 8.0})
    assert any(f["rule_id"] == "ho_prep_failure" for f in findings)


def test_throughput_low_cqi_bler():
    findings = THROUGHPUT_RULE_ENGINE.evaluate({"cqi": 7.0, "bler": 15.0})
    assert any(f["rule_id"] == "tput_low_cqi_bler" for f in findings)


def test_call_drop_beam():
    findings = CALL_DROP_RULE_ENGINE.evaluate({"beam_failure_ratio": 35, "call_drop_rate": 3})
    assert any("beam" in f["rule_id"] for f in findings)


def test_detect_issue():
    assert detect_issue_type("handover failure on cell 43211") == "handover"
    assert detect_issue_type("low throughput CQI bler") == "throughput"
    assert detect_issue_type("RACH msg3 failure") == "rach"


if __name__ == "__main__":
    test_ho_prep_failure()
    test_throughput_low_cqi_bler()
    test_call_drop_beam()
    test_detect_issue()
    print("All rule tests passed.")
