"""Radio Link Failure (RLF) rules engine."""

from __future__ import annotations

from tnic.rules.engine import RuleDefinition, RuleEngine, _get


def _rlf_rules() -> list[RuleDefinition]:
    cat = "rlf"

    return [
        RuleDefinition(
            "rlf_coverage_hole", cat, "Coverage hole RLF",
            lambda k: (_get(k, "ss_rsrp") or 0) < -110 and (_get(k, "rlf_rate") or 0) > 1,
            "RLF driven by coverage hole — RSRP below cell-edge threshold",
            0.84, ["Coverage audit on RLF cluster", "Consider small cell or tilt optimization"],
            ["ss_rsrp", "rlf_rate"],
        ),
        RuleDefinition(
            "rlf_interference", cat, "Interference RLF",
            lambda k: (_get(k, "ss_rsrp") or -999) > -100 and (_get(k, "ss_sinr") or 99) < 5,
            "Good RSRP but poor SINR — interference-induced RLF",
            0.79, ["Identify dominant interferer PCI", "Adjust tilt or PCI plan"],
            ["ss_rsrp", "ss_sinr"],
        ),
        RuleDefinition(
            "rlf_t310_n310", cat, "T310/N310 sync failure",
            lambda k: (_get(k, "out_of_sync_events") or 0) > 5 or (_get(k, "rlf_after_sync_fail") or 0) > 0,
            "RLF after out-of-sync — T310/N310 timer expiry pattern",
            0.77, ["Review N310/N311 counters", "Check DL quality at RLF geo"],
            ["out_of_sync_events", "rlf_after_sync_fail"],
        ),
        RuleDefinition(
            "rlf_after_ho", cat, "RLF after handover",
            lambda k: (_get(k, "rlf_after_ho_rate") or 0) > 2,
            "RLF cluster after handover — target cell not sustainable",
            0.81, ["Audit target cell RF post-HO", "Tune HO margins"],
            ["rlf_after_ho_rate"],
        ),
    ]


RLF_RULE_ENGINE = RuleEngine("rlf", _rlf_rules())
