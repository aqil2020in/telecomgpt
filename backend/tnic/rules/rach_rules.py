"""RACH rules engine — MSG1-MSG4, PRACH config, access delay, beam."""

from __future__ import annotations

from tnic.rules.engine import RuleDefinition, RuleEngine, _get


def _rach_rules() -> list[RuleDefinition]:
    cat = "rach"

    return [
        RuleDefinition(
            "rach_msg1_fail", cat, "MSG1 preamble fail",
            lambda k: (_get(k, "rach_msg1_fail_rate") or 0) > 5,
            "High MSG1/preamble failure — PRACH not detected at gNB",
            0.8, ["Check PRACH power ramping", "Verify root sequence config"],
            ["rach_msg1_fail_rate"],
        ),
        RuleDefinition(
            "rach_msg3_fail", cat, "MSG3 failure",
            lambda k: (_get(k, "rach_msg3_fail_rate") or 0) > 3,
            "MSG3 failures — TA misalignment or PUSCH collision",
            0.82, ["Review timing advance values", "Check PRACH occasion collision"],
            ["rach_msg3_fail_rate"],
        ),
        RuleDefinition(
            "rach_low_success", cat, "Overall RACH failure",
            lambda k: (_get(k, "rach_success_rate") or 100) < 90,
            "RACH success rate below threshold",
            0.77, ["Audit prach-ConfigurationIndex in SIB1", "Compare PRACH SINR vs threshold"],
            ["rach_success_rate"],
        ),
        RuleDefinition(
            "rach_access_delay", cat, "Access delay",
            lambda k: (_get(k, "rach_access_delay_ms") or 0) > 200,
            "Excessive RACH access delay — contention or config issue",
            0.7, ["Review RACH occasion density", "Check cell load at access"],
            ["rach_access_delay_ms"],
        ),
        RuleDefinition(
            "rach_beam", cat, "Beam-related RACH",
            lambda k: (_get(k, "rach_beam_fail_rate") or 0) > 2 and (_get(k, "beam_failure_ratio") or 0) > 20,
            "Beam-related RACH failures — SSB/beam selection mismatch",
            0.74, ["Verify SSB beam sweep", "Check beam correspondence for PRACH"],
            ["rach_beam_fail_rate", "beam_failure_ratio"],
        ),
        RuleDefinition(
            "rach_rrc_setup_fail", cat, "RRC setup failure",
            lambda k: (_get(k, "rrc_setup_fail_rate") or 0) > 3 or (
                (_get(k, "rach_success_rate") or 100) < 92 and (_get(k, "ss_rsrp") or -80) < -105
            ),
            "High RRC setup failure — accessibility blocked after RACH",
            0.78, ["Check SIB1 broadcast", "Verify cell barring/load", "Review AMF reachability"],
            ["rrc_setup_fail_rate", "rach_success_rate", "ss_rsrp"],
        ),
        RuleDefinition(
            "rach_prach_config", cat, "PRACH config mismatch",
            lambda k: (_get(k, "prach_conflict_count") or 0) > 0,
            "PRACH configuration conflict — MSG1 detection degraded",
            0.76, ["Audit prach-RootSequenceIndex", "Coordinate PCI/PRACH plan with ANR"],
            ["prach_conflict_count", "rach_msg1_fail_rate"],
        ),
    ]


RACH_RULE_ENGINE = RuleEngine("rach", _rach_rules())
