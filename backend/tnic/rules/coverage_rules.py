"""PM-based coverage rules — hole, overshoot, pilot pollution, interference."""

from __future__ import annotations

from tnic.rules.engine import RuleDefinition, RuleEngine, _get


def _coverage_rules() -> list[RuleDefinition]:
    cat = "coverage"

    return [
        RuleDefinition(
            "cov_coverage_hole", cat, "Coverage hole",
            lambda k: (_get(k, "ss_rsrp") or 0) < -110 or (_get(k, "coverage_hole_pct") or 0) > 5,
            "Coverage hole — RSRP below -110 dBm or elevated hole percentage in drive data",
            0.86,
            ["Retilt or add filler/small cell", "Re-drive cluster to confirm geography"],
            ["ss_rsrp", "coverage_hole_pct"],
        ),
        RuleDefinition(
            "cov_overshooting", cat, "Overshooting cell",
            lambda k: (
                ((_get(k, "distance_miles") or 0) > 2.5 and (_get(k, "ss_rsrp") or -999) > -90)
                or (_get(k, "ho_too_early_rate") or 0) > 3 and (_get(k, "ss_rsrp") or -999) > -92
                or (_get(k, "overshoot_indicator") or 0) > 0
            ),
            "Overshooting cell — strong RSRP far from site or correlated too-early HO",
            0.80,
            ["Reduce tilt/power to shrink footprint", "Tune A3/TTT mobility parameters"],
            ["distance_miles", "ss_rsrp", "ho_too_early_rate", "overshoot_indicator"],
        ),
        RuleDefinition(
            "cov_pilot_pollution", cat, "Pilot pollution",
            lambda k: (
                (_get(k, "pilot_pollution_index") or 0) > 0.5
                or ((_get(k, "ss_rsrp") or -999) > -95 and (_get(k, "ss_sinr") or 99) < 0)
                or (_get(k, "dominant_pilot_count") or 0) >= 3
            ),
            "Pilot pollution — multiple strong pilots at similar level degrading SINR",
            0.82,
            ["PCI replan and CIO tuning", "Reduce overlap between dominant servers"],
            ["pilot_pollution_index", "ss_rsrp", "ss_sinr", "dominant_pilot_count"],
        ),
        RuleDefinition(
            "cov_interference", cat, "RF interference",
            lambda k: (_get(k, "ss_sinr") or 99) <= -5 and (_get(k, "ss_rsrp") or -999) > -110,
            "RF interference — degraded SINR despite usable RSRP",
            0.84,
            ["Run PCI/mod-3 scan", "Identify co-channel or external interferer"],
            ["ss_sinr", "ss_rsrp", "bler"],
        ),
    ]


COVERAGE_RULE_ENGINE = RuleEngine("coverage", _coverage_rules())
