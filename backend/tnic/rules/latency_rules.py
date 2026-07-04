"""Latency rules engine — air, Xn, N2, CU/DU, UPF, Internet."""

from __future__ import annotations

from tnic.rules.engine import RuleDefinition, RuleEngine, _get


def _latency_rules() -> list[RuleDefinition]:
    cat = "latency"

    return [
        RuleDefinition(
            "lat_air_interface", cat, "Air interface latency",
            lambda k: (_get(k, "air_latency_ms") or 0) > 20,
            "High air-interface latency — scheduling or HARQ retx delay",
            0.72, ["Check BLER and HARQ retx rate", "Review mini-slot / URLLC config if applicable"],
            ["air_latency_ms"],
        ),
        RuleDefinition(
            "lat_xn", cat, "Xn latency",
            lambda k: (_get(k, "xn_latency_ms") or 0) > 15,
            "Elevated Xn interface latency — inter-gNB coordination delay",
            0.74, ["Check Xn transport QoS", "Verify fronthaul/backhaul on Xn path"],
            ["xn_latency_ms"],
        ),
        RuleDefinition(
            "lat_n2", cat, "N2 latency",
            lambda k: (_get(k, "n2_latency_ms") or 0) > 25,
            "N2 (NGAP) latency spike — AMF interaction delay",
            0.71, ["Check AMF load", "Review NGAP procedure timers"],
            ["n2_latency_ms"],
        ),
        RuleDefinition(
            "lat_cudu", cat, "CU-DU latency",
            lambda k: (_get(k, "cudu_latency_ms") or 0) > 10,
            "CU-DU split latency — F1/eCPRI delay elevated",
            0.75, ["Verify F1 transport", "Check DU pool load"],
            ["cudu_latency_ms"],
        ),
        RuleDefinition(
            "lat_upf", cat, "UPF latency",
            lambda k: (_get(k, "upf_latency_ms") or _get(k, "latency_ms") or 0) > 50,
            "UPF user-plane latency spike — core processing or load",
            0.82, ["Rebalance UPF cluster", "Check UPF CPU during peak hours"],
            ["upf_latency_ms", "latency_ms"],
        ),
        RuleDefinition(
            "lat_internet", cat, "Internet/N6 latency",
            lambda k: (_get(k, "n6_latency_ms") or 0) > 80,
            "N6/Internet path latency — external breakout delay",
            0.68, ["Check peering and DNS", "Verify N6 QoS marking"],
            ["n6_latency_ms"],
        ),
        RuleDefinition(
            "lat_qos_mismatch", cat, "QoS misclassification",
            lambda k: (_get(k, "qos_mismatch_flag") or 0) > 0,
            "QoS flow mapped to non-GBR 5QI — latency SLA at risk",
            0.79, ["Correct 5QI mapping for GBR service", "Verify SMF QoS rules"],
            ["qos_mismatch_flag"],
        ),
    ]


LATENCY_RULE_ENGINE = RuleEngine("latency", _latency_rules())
