"""Core network rules — PDU session, NG/N2, AMF/SMF."""

from __future__ import annotations

from tnic.rules.engine import RuleDefinition, RuleEngine, _get


def _core_rules() -> list[RuleDefinition]:
    cat = "core"

    return [
        RuleDefinition(
            "core_pdu_session_fail", cat, "PDU session setup failure",
            lambda k: (_get(k, "pdu_session_fail_rate") or 0) > 2,
            "PDU session setup failure — SMF/AMF session management issue",
            0.81,
            ["Inspect SMF session logs", "Verify DNN/slice configuration", "Check UPF selection"],
            ["pdu_session_fail_rate"],
        ),
        RuleDefinition(
            "core_ng_n2_failure", cat, "NG/N2 interface failure",
            lambda k: (
                (_get(k, "ho_n2_fail_rate") or 0) > 2
                or (_get(k, "ngap_failure_count") or 0) > 0
                or (_get(k, "amf_release_rate") or 0) > 0.5
            ),
            "NG/N2 failure — NGAP errors or AMF-initiated release spike",
            0.79,
            ["Check AMF pool load and NGAP timers", "Verify N2 SCTP connectivity", "Review 5GMM cause codes"],
            ["ho_n2_fail_rate", "ngap_failure_count", "amf_release_rate"],
        ),
        RuleDefinition(
            "core_upf_latency", cat, "UPF user-plane latency",
            lambda k: (_get(k, "upf_latency_ms") or 0) > 40,
            "UPF latency elevated — user-plane processing delay",
            0.78,
            ["Rebalance UPF cluster", "Scale UPF instances", "Check N6 path"],
            ["upf_latency_ms"],
        ),
        RuleDefinition(
            "core_amf_overload", cat, "AMF overload pattern",
            lambda k: (_get(k, "amf_release_rate") or 0) > 1 and (_get(k, "rrc_setup_fail_rate") or 0) > 3,
            "AMF overload correlated with RRC setup failures",
            0.74,
            ["Scale AMF pool", "Review admission control", "Check N2 capacity"],
            ["amf_release_rate", "rrc_setup_fail_rate"],
        ),
    ]


CORE_RULE_ENGINE = RuleEngine("core", _core_rules())
