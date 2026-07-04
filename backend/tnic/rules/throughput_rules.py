"""Throughput rules engine — CQI, MCS, BLER, scheduler, backhaul."""

from __future__ import annotations

from tnic.rules.engine import RuleDefinition, RuleEngine, _get


def _throughput_rules() -> list[RuleDefinition]:
    cat = "throughput"

    return [
        RuleDefinition(
            "tput_low_cqi_bler", cat, "Low CQI + high BLER",
            lambda k: (_get(k, "cqi") or 99) < 8 and (_get(k, "bler") or 0) > 10,
            "Throughput limited by poor radio — low CQI with high DL BLER",
            0.85, ["Recalibrate AAU", "Check interference PCI", "Verify MIMO rank"],
            ["cqi", "bler", "throughput_mbps"],
        ),
        RuleDefinition(
            "tput_stuck_rank1", cat, "MIMO rank-1 stuck",
            lambda k: (_get(k, "ri") or 99) <= 1.2 and (_get(k, "throughput_mbps") or 999) < 50,
            "MIMO stuck at rank-1 — layer adaptation not scaling",
            0.78, ["Validate antenna calibration", "Review RI/CQI reporting"],
            ["ri", "throughput_mbps"],
        ),
        RuleDefinition(
            "tput_low_mcs", cat, "Low MCS",
            lambda k: (_get(k, "mcs") or 99) < 12 and (_get(k, "ss_sinr") or 99) < 10,
            "Low MCS assignment — scheduler capped by SINR/CQI",
            0.73, ["Improve SINR at serving cell", "Check scheduler PRB allocation"],
            ["mcs", "ss_sinr"],
        ),
        RuleDefinition(
            "tput_congestion", cat, "Scheduler congestion",
            lambda k: (_get(k, "prb_utilization") or 0) > 85,
            "High PRB utilization — scheduler congestion limiting throughput",
            0.71, ["Offload traffic via HO/CA", "Add capacity carrier"],
            ["prb_utilization", "throughput_mbps"],
        ),
        RuleDefinition(
            "tput_backhaul", cat, "Backhaul bottleneck",
            lambda k: (_get(k, "backhaul_utilization") or 0) > 80 and (_get(k, "cqi") or 0) > 10,
            "Good RF but backhaul saturated — transport bottleneck",
            0.75, ["Upgrade N3 link", "Check UPF/cluster throughput"],
            ["backhaul_utilization", "cqi"],
        ),
    ]


THROUGHPUT_RULE_ENGINE = RuleEngine("throughput", _throughput_rules())
