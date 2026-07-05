"""Radio Link Failure (RLF) rules engine."""

from __future__ import annotations

from tnic.rules.engine import RuleDefinition, RuleEngine, _get


def _rsrp(k):
    return _get(k, "rlf_rsrp_mean") if _get(k, "rlf_rsrp_mean") is not None else _get(k, "ss_rsrp")


def _sinr(k):
    return _get(k, "rlf_sinr_mean") if _get(k, "rlf_sinr_mean") is not None else _get(k, "ss_sinr")


def _rlf_rules() -> list[RuleDefinition]:
    cat = "rlf"

    return [
        RuleDefinition(
            "rlf_coverage_hole", cat, "Coverage hole RLF",
            lambda k: (_rsrp(k) or 0) < -110 and (_get(k, "rlf_rate") or 0) > 1,
            "RLF driven by coverage hole — RSRP below cell-edge threshold",
            0.84, ["Coverage audit on RLF cluster", "Consider small cell or tilt optimization"],
            ["rlf_rsrp_mean", "ss_rsrp", "rlf_rate"],
        ),
        RuleDefinition(
            "rlf_coverage_cause", cat, "Coverage-classified RLF",
            lambda k: (_get(k, "rlf_coverage_pct") or 0) > 20,
            "High proportion of Coverage-tagged RLF events — cell-edge or hole pattern",
            0.82, ["Drive-test RLF cluster geography", "Review antenna tilt and power"],
            ["rlf_coverage_pct"],
        ),
        RuleDefinition(
            "rlf_interference", cat, "Interference RLF",
            lambda k: (_rsrp(k) or -999) > -100 and (_sinr(k) or 99) < 5,
            "Good RSRP but poor SINR — interference-induced RLF",
            0.79, ["Identify dominant interferer PCI", "Adjust tilt or PCI plan"],
            ["rlf_sinr_mean", "ss_sinr", "rlf_rsrp_mean", "ss_rsrp"],
        ),
        RuleDefinition(
            "rlf_interference_cause", cat, "Interference-classified RLF",
            lambda k: (_get(k, "rlf_interference_pct") or 0) > 20,
            "High proportion of Interference-tagged RLF events — co-channel or adjacent-sector",
            0.8, ["Run PCI/RF interference scan", "Check mod-3 and beam overlap"],
            ["rlf_interference_pct"],
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
            lambda k: (_get(k, "rlf_after_ho_rate") or _get(k, "rlf_post_ho_pct") or 0) > 15,
            "RLF cluster after handover — target cell not sustainable",
            0.81, ["Audit target cell RF post-HO", "Tune HO margins"],
            ["rlf_after_ho_rate", "rlf_post_ho_pct"],
        ),
        RuleDefinition(
            "rlf_transport_flap", cat, "Transport flap induced RLF",
            lambda k: (_get(k, "transport_loss_rate") or 0) > 0.3 and (_get(k, "rlf_rate") or 0) > 1,
            "Transport packet loss correlated with RLF — backhaul instability",
            0.75, ["Check fronthaul/backhaul alarms", "Verify SCTP/GTP stability"],
            ["transport_loss_rate", "rlf_rate"],
        ),
    ]


RLF_RULE_ENGINE = RuleEngine("rlf", _rlf_rules())
