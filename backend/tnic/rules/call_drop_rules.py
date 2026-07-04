"""Call drop rules engine — radio, mobility, core, IMS, transport."""

from __future__ import annotations

from tnic.rules.engine import RuleDefinition, RuleEngine, _get


def _call_drop_rules() -> list[RuleDefinition]:
    cat = "call_drop"

    def mobility(k):
        return (_get(k, "drop_mobility_pct") or 0) > 15 or (
            (_get(k, "call_drop_rate") or 0) > 2 and (_get(k, "ho_success_rate") or 100) < 92
        )

    def radio(k):
        return (_get(k, "drop_radio_pct") or 0) > 15 or (
            (_get(k, "call_drop_rate") or 0) > 2 and (_get(k, "rlf_rate") or 0) > 1
        )

    def core(k):
        return (_get(k, "drop_core_pct") or 0) > 15 or (
            (_get(k, "amf_release_rate") or 0) > 1 and (_get(k, "ss_rsrp") or -80) > -95
        )

    def ims(k):
        return (_get(k, "drop_ims_pct") or _get(k, "ims_drop_rate") or 0) > 15

    def transport(k):
        return (_get(k, "drop_transport_pct") or 0) > 10 or (_get(k, "transport_loss_rate") or 0) > 0.5

    return [
        RuleDefinition(
            "drop_mobility", cat, "Mobility-related drop",
            mobility,
            "Mobility-related call drops — HO failure or ping-pong leading to release",
            0.78, ["Audit HO success on drop route", "Add missing neighbor", "Review too-late HO margin"],
            ["drop_mobility_pct", "call_drop_rate", "ho_success_rate"],
        ),
        RuleDefinition(
            "drop_radio", cat, "Radio layer drop",
            radio,
            "Radio layer call drops — RLF or RF degradation leading to release",
            0.83, ["Correlate drops with RSRP/SINR", "Review re-establishment success", "Run RLF RCA"],
            ["drop_radio_pct", "call_drop_rate", "rlf_rate"],
        ),
        RuleDefinition(
            "drop_radio_rlf", cat, "Radio RLF drop",
            lambda k: (_get(k, "call_drop_rate") or 0) > 2 and (_get(k, "rlf_rate") or 0) > 1,
            "Call drops correlated with RLF — radio layer release",
            0.83, ["Correlate drops with RSRP/SINR", "Review re-establishment success"],
            ["call_drop_rate", "rlf_rate"],
        ),
        RuleDefinition(
            "drop_beam_failure", cat, "Beam failure drop",
            lambda k: (_get(k, "beam_failure_ratio") or 0) > 30,
            "High beam failure ratio driving context release",
            0.8, ["Check beam weights and tilt", "Validate beam management KPIs"],
            ["beam_failure_ratio", "call_drop_rate"],
        ),
        RuleDefinition(
            "drop_core", cat, "Core network drop",
            core,
            "Core-initiated call drop — AMF/SMF release with healthy RAN RF",
            0.74, ["Check AMF release cause", "Verify subscription and PDU session state"],
            ["drop_core_pct", "amf_release_rate", "ss_rsrp"],
        ),
        RuleDefinition(
            "drop_core_amf", cat, "Core AMF release",
            core,
            "Core-side AMF release with healthy RAN RF — investigate 5GMM cause",
            0.72, ["Check AMF release cause", "Verify subscription and PDU session state"],
            ["amf_release_rate", "ss_rsrp", "drop_core_pct"],
        ),
        RuleDefinition(
            "drop_transport", cat, "Transport drop",
            transport,
            "Transport/backhaul drop — N3/N6 packet loss or congestion",
            0.72, ["Check N3/N6 utilization", "Verify backhaul QoS", "Inspect transport loss counters"],
            ["drop_transport_pct", "transport_loss_rate"],
        ),
        RuleDefinition(
            "drop_ims", cat, "IMS/VoNR drop",
            ims,
            "IMS/VoNR specific drop — check 5QI-1 bearer and IMS registration",
            0.76, ["Verify VoNR EPS fallback", "Check IMS P-CSCF path"],
            ["drop_ims_pct", "ims_drop_rate"],
        ),
    ]


CALL_DROP_RULE_ENGINE = RuleEngine("call_drop", _call_drop_rules())
