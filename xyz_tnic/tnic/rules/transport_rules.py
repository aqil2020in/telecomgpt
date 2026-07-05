"""Transport rules engine — backhaul, Xn SCTP, packet loss."""

from __future__ import annotations

from tnic.rules.engine import RuleDefinition, RuleEngine, _get


def _transport_rules() -> list[RuleDefinition]:
    cat = "transport"

    return [
        RuleDefinition(
            "transport_congestion", cat, "Transport congestion",
            lambda k: (_get(k, "backhaul_utilization") or 0) > 75 or (_get(k, "n3_utilization") or 0) > 80,
            "Transport congestion — N3/F1/backhaul utilization above threshold",
            0.78,
            ["Upgrade transport link", "Enable QoS on N3/F1", "Offload traffic to alternate path"],
            ["backhaul_utilization", "n3_utilization"],
        ),
        RuleDefinition(
            "transport_loss", cat, "Transport packet loss",
            lambda k: (_get(k, "transport_loss_rate") or 0) > 0.3,
            "Packet loss on transport path — GTP/SCTP instability",
            0.76,
            ["Check switch/router counters", "Verify MTU and fragmentation", "Inspect SCTP retransmissions"],
            ["transport_loss_rate"],
        ),
        RuleDefinition(
            "transport_xn_sctp", cat, "Xn SCTP transport failure",
            lambda k: (_get(k, "ho_xn_fail_rate") or 0) > 2 and (_get(k, "xn_latency_ms") or 0) > 50,
            "Xn HO failures with elevated Xn latency — SCTP/IPsec path issue",
            0.79,
            ["Verify Xn IPsec/SCTP endpoints", "Check firewall and routing on Xn", "Review Xn neighbor config"],
            ["ho_xn_fail_rate", "xn_latency_ms"],
        ),
        RuleDefinition(
            "transport_f1_degraded", cat, "F1 fronthaul degraded",
            lambda k: (_get(k, "f1_latency_ms") or 0) > 5 or (_get(k, "f1_packet_loss_pct") or 0) > 0.1,
            "F1 fronthaul latency or loss elevated — DU-CU link stress",
            0.77,
            ["Check eCPRI/fronthaul switch", "Verify DU-CU sync", "Inspect F1-U packet loss"],
            ["f1_latency_ms", "f1_packet_loss_pct"],
        ),
    ]


TRANSPORT_RULE_ENGINE = RuleEngine("transport", _transport_rules())
