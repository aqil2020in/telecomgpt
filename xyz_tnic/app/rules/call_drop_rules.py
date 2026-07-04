"""Call drop rules engine — radio, mobility, core, IMS, transport."""

from __future__ import annotations

from app.rules.engine import RuleDefinition, RuleEngine, _get


def _call_drop_rules() -> list[RuleDefinition]:
    cat = "call_drop"

    return [
        RuleDefinition(
            "drop_radio_rlf", cat, "Radio RLF drop",
            lambda k: (_get(k, "call_drop_rate") or 0) > 2 and (_get(k, "rlf_rate") or 0) > 1,
            "Call drops correlated with RLF — radio layer release",
            0.83, ["Correlate drops with RSRP/SINR", "Review re-establishment success"],
            ["call_drop_rate", "rlf_rate"],
        ),
        RuleDefinition(
            "drop_mobility", cat, "Mobility-related drop",
            lambda k: (_get(k, "call_drop_rate") or 0) > 2 and (_get(k, "ho_success_rate") or 100) < 92,
            "Drops during mobility — HO failure leading to release",
            0.76, ["Audit HO success on drop route", "Add missing neighbor"],
            ["call_drop_rate", "ho_success_rate"],
        ),
        RuleDefinition(
            "drop_beam_failure", cat, "Beam failure drop",
            lambda k: (_get(k, "beam_failure_ratio") or 0) > 30,
            "High beam failure ratio driving context release",
            0.8, ["Check beam weights and tilt", "Validate beam management KPIs"],
            ["beam_failure_ratio", "call_drop_rate"],
        ),
        RuleDefinition(
            "drop_core_amf", cat, "Core AMF release",
            lambda k: (_get(k, "amf_release_rate") or 0) > 1 and (_get(k, "ss_rsrp") or -80) > -95,
            "Core-side AMF release with healthy RAN RF — investigate 5GMM cause",
            0.72, ["Check AMF release cause", "Verify subscription and PDU session state"],
            ["amf_release_rate", "ss_rsrp"],
        ),
        RuleDefinition(
            "drop_transport", cat, "Transport drop",
            lambda k: (_get(k, "transport_loss_rate") or 0) > 0.5,
            "Transport packet loss contributing to session drop",
            0.7, ["Check N3/N6 utilization", "Verify backhaul QoS"],
            ["transport_loss_rate"],
        ),
        RuleDefinition(
            "drop_ims", cat, "IMS/VoNR drop",
            lambda k: (_get(k, "ims_drop_rate") or 0) > 1,
            "IMS/VoNR specific drop — check 5QI-1 bearer and IMS registration",
            0.74, ["Verify VoNR EPS fallback", "Check IMS P-CSCF path"],
            ["ims_drop_rate"],
        ),
    ]


CALL_DROP_RULE_ENGINE = RuleEngine("call_drop", _call_drop_rules())
