"""Beamforming rules engine — overload, imbalance, coverage, instability."""

from __future__ import annotations

from app.rules.engine import RuleDefinition, RuleEngine, _get


def _beamforming_rules() -> list[RuleDefinition]:
    cat = "beamforming"

    return [
        RuleDefinition(
            "beam_overload", cat, "Beam overload",
            lambda k: (_get(k, "beam_load_pct") or 0) > 90,
            "Beam overload — single beam carrying excessive traffic",
            0.76, ["Rebalance traffic across beams", "Review beam-specific scheduler weights"],
            ["beam_load_pct"],
        ),
        RuleDefinition(
            "beam_imbalance", cat, "Beam imbalance",
            lambda k: (_get(k, "beam_imbalance_ratio") or 0) > 2.5,
            "Beam load imbalance — uneven distribution across SSB beams",
            0.73, ["Adjust beam weights", "Verify AAU calibration"],
            ["beam_imbalance_ratio"],
        ),
        RuleDefinition(
            "beam_coverage_gap", cat, "Beam coverage gap",
            lambda k: (_get(k, "beam_coverage_gap_pct") or 0) > 15,
            "Coverage gaps between beams — geo holes in beam footprint",
            0.78, ["Optimize tilt/azimuth per beam", "Add relay or small cell"],
            ["beam_coverage_gap_pct"],
        ),
        RuleDefinition(
            "beam_instability", cat, "Beam instability",
            lambda k: (_get(k, "beam_switch_rate") or 0) > 10 and (_get(k, "beam_failure_ratio") or 0) > 25,
            "Frequent beam switches with high failure ratio — unstable beam management",
            0.8, ["Tune beam management timers", "Check SSB-RSRP hysteresis"],
            ["beam_switch_rate", "beam_failure_ratio"],
        ),
        RuleDefinition(
            "beam_health_low", cat, "Low beam health score",
            lambda k: (_get(k, "beam_health_score") or 100) < 60,
            "Composite beam health score below threshold",
            0.77, ["Run beam health audit", "Recalibrate massive MIMO array"],
            ["beam_health_score"],
        ),
    ]


BEAMFORMING_RULE_ENGINE = RuleEngine("beamforming", _beamforming_rules())
