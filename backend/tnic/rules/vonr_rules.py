"""VoNR / IMS voice rules engine — 5G SA voice bearer RCA."""

from __future__ import annotations

from tnic.rules.engine import RuleDefinition, RuleEngine, _get


def _vonr_rules() -> list[RuleDefinition]:
    cat = "vonr"

    return [
        RuleDefinition(
            "vonr_drop", cat, "VoNR call drop",
            lambda k: (_get(k, "vonr_drop_rate") or 0) > 1.5 or (_get(k, "drop_ims_pct") or 0) > 5,
            "VoNR/IMS call drop rate elevated — voice bearer or mobility-induced drop",
            0.85,
            ["Check 5QI-1 bearer stability", "Correlate drops with HO/RLF events", "Improve NR voice coverage"],
            ["vonr_drop_rate", "drop_ims_pct"],
        ),
        RuleDefinition(
            "vonr_setup_fail", cat, "VoNR QoS flow setup failure",
            lambda k: (_get(k, "vonr_setup_success_rate") or 100) < 95,
            "VoNR session setup success below 95% — 5QI-1/65 flow or SMF path issue",
            0.84,
            ["Verify 5QI-1 profile on SMF", "Check IMS registration via 5G path", "Audit UPF QoS mapping"],
            ["vonr_setup_success_rate", "ims_registration_rate"],
        ),
        RuleDefinition(
            "vonr_ims_reg_fail", cat, "IMS registration failure",
            lambda k: (_get(k, "ims_registration_rate") or 100) < 98,
            "IMS registration failure — VoLTE/VoNR attach path blocked",
            0.82,
            ["Check P-CSCF/SBC reachability", "Verify UE IMS APN", "Inspect SIP 403/408 responses"],
            ["ims_registration_rate"],
        ),
        RuleDefinition(
            "vonr_coverage_hole", cat, "VoNR coverage hole",
            lambda k: (_get(k, "ss_rsrp") or -80) < -110 and (_get(k, "vonr_drop_rate") or 0) > 2,
            "VoNR drops in weak NR coverage — edge RSRP below voice threshold",
            0.86,
            ["Improve NR indoor/edge coverage", "Enable EPS fallback if VoNR not sustainable", "Retilt/filler cell"],
            ["ss_rsrp", "vonr_drop_rate"],
        ),
        RuleDefinition(
            "vonr_rtp_loss", cat, "RTP packet loss / mute",
            lambda k: (_get(k, "rtp_packet_loss_pct") or 0) > 1 or (_get(k, "voice_mute_rate") or 0) > 0.5,
            "RTP one-way or high packet loss — mute call / poor MOS",
            0.80,
            ["Check QoS scheduler for 5QI-1", "Verify DSCP/QFI end-to-end", "Trace UPF/IMS firewall"],
            ["rtp_packet_loss_pct", "voice_mute_rate"],
        ),
        RuleDefinition(
            "vonr_srvcc_fail", cat, "SRVCC/eSRVCC handover failure",
            lambda k: (_get(k, "srvcc_fail_rate") or 0) > 3,
            "SRVCC failure during LTE↔NR voice mobility",
            0.78,
            ["Optimize SRVCC parameters", "Verify MME/AMF voice anchor", "Check inter-RAT neighbor plan"],
            ["srvcc_fail_rate"],
        ),
        RuleDefinition(
            "vonr_amf_smf_session", cat, "AMF/SMF PDU session failure for voice",
            lambda k: (_get(k, "pdu_session_fail_rate") or 0) > 2 and (_get(k, "vonr_setup_success_rate") or 100) < 97,
            "PDU session setup failure blocking VoNR bearer",
            0.79,
            ["Check SMF session management logs", "Verify slice/DNN for IMS", "Review AMF 5GMM cause"],
            ["pdu_session_fail_rate", "vonr_setup_success_rate"],
        ),
    ]


VONR_RULE_ENGINE = RuleEngine("vonr", _vonr_rules())
