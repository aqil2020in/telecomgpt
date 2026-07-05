"""Handover (HO) rules engine."""

from __future__ import annotations

from tnic.rules.engine import RuleDefinition, RuleEngine, _get


def _ho_rules() -> list[RuleDefinition]:
    cat = "handover"

    def prep_fail(k):
        rate = _get(k, "ho_prep_fail_rate")
        return rate is not None and rate > 5.0

    def exec_fail(k):
        rate = _get(k, "ho_exec_fail_rate")
        if rate is not None and rate > 2.0:
            return True
        success = _get(k, "ho_success_rate")
        return success is not None and success < 95.0

    def too_early(k):
        return _get(k, "ho_too_early_rate", 0) > 3.0

    def too_late(k):
        return _get(k, "ho_too_late_rate", 0) > 3.0

    def ping_pong(k):
        return _get(k, "ho_ping_pong_rate", 0) > 5.0

    def wrong_cell(k):
        return _get(k, "ho_wrong_cell_rate", 0) > 2.0

    def weak_target(k):
        rsrp = _get(k, "target_rsrp")
        return rsrp is not None and rsrp < -110

    def xn_fail(k):
        return _get(k, "ho_xn_fail_rate", 0) > 2.0

    def n2_fail(k):
        return _get(k, "ho_n2_fail_rate", 0) > 2.0

    return [
        RuleDefinition("ho_prep_failure", cat, "HO preparation failure",
                       prep_fail, "High HO preparation failure — target cell not ready or Xn/NG timeout",
                       0.82, ["Verify Xn connectivity", "Check neighbor relation for target PCI", "Review HO prep timer"],
                       ["ho_prep_fail_rate"]),
        RuleDefinition("ho_execution_failure", cat, "HO execution failure",
                       exec_fail, "HO execution failure — RF or procedure failure during mobility",
                       0.78, ["Compare source/target RSRP at HO", "Audit HO parameters A3/A5", "Drive-test HO corridor"],
                       ["ho_exec_fail_rate", "ho_success_rate"]),
        RuleDefinition("ho_xn_failure", cat, "Xn interface HO failure",
                       xn_fail, "Xn interface HO failure — inter-gNB XnAP prep or setup timeout",
                       0.8, ["Check Xn transport and IPsec/SCTP", "Verify Xn neighbor relation", "Review XnAP cause codes"],
                       ["ho_xn_fail_rate"]),
        RuleDefinition("ho_n2_failure", cat, "N2/NGAP HO failure",
                       n2_fail, "N2 NGAP HO failure — AMF or gNB NG interface issue during HO",
                       0.77, ["Check AMF load and NGAP timers", "Verify N2 connectivity", "Inspect NGAP HandoverFailure cause"],
                       ["ho_n2_fail_rate"]),
        RuleDefinition("ho_too_early", cat, "Too early HO",
                       too_early, "Too-early handovers — mobility threshold too aggressive",
                       0.71, ["Increase A3 offset or time-to-trigger", "Review cell individual offsets"],
                       ["ho_too_early_rate"]),
        RuleDefinition("ho_too_late", cat, "Too late HO",
                       too_late, "Too-late handovers — UE reaches cell edge before HO trigger",
                       0.73, ["Decrease A3 offset", "Add filler cell on HO corridor"],
                       ["ho_too_late_rate"]),
        RuleDefinition("ho_ping_pong", cat, "Ping-pong HO",
                       ping_pong, "Ping-pong handovers between neighbors — hysteresis mis-tuned",
                       0.76, ["Increase hysteresis", "Review CIO between neighbor pair"],
                       ["ho_ping_pong_rate"]),
        RuleDefinition("ho_wrong_cell", cat, "Wrong cell selection",
                       wrong_cell, "HO to suboptimal cell — wrong cell ranking or missing best neighbor",
                       0.69, ["Verify neighbor list completeness", "Check SSB beam priority"],
                       ["ho_wrong_cell_rate"]),
        RuleDefinition("ho_weak_target_rf", cat, "Weak target RF",
                       weak_target, "Target cell RSRP too weak at HO decision — coverage gap",
                       0.8, ["Close coverage gap", "Adjust mobility thresholds"],
                       ["target_rsrp"]),
        RuleDefinition("ho_missing_neighbor", cat, "Missing neighbor",
                       lambda k: (_get(k, "nr_neighbor_count") or 99) < 3 and (_get(k, "ho_prep_fail_rate") or 0) > 3,
                       "Missing neighbor relation — HO prep fails to undefined target",
                       0.81, ["Add NCR via ANR or manual plan", "Validate neighbor allow-list"],
                       ["nr_neighbor_count", "ho_prep_fail_rate"]),
        RuleDefinition("ho_pci_collision", cat, "PCI collision at HO",
                       lambda k: (_get(k, "pci_conflict_count") or 0) > 0,
                       "PCI collision/confusion — HO to wrong PCI or measurement confusion",
                       0.79, ["PCI replan", "Enable ANR PCI correction"],
                       ["pci_conflict_count", "ho_wrong_cell_rate"]),
        RuleDefinition("ho_post_ho_rlf", cat, "Post-HO RLF",
                       lambda k: (_get(k, "ho_post_ho_rlf_rate") or 0) > 3.0,
                       "Post-handover RLF — T310 expiry after mobility reconfiguration",
                       0.81, ["Review HO corridor RF", "Check reconfigurationWithSync success", "Audit T310/N310"],
                       ["ho_post_ho_rlf_rate", "rlf_after_ho_rate"]),
        RuleDefinition("ho_coverage_induced", cat, "Coverage-induced HO failure",
                       lambda k: (_get(k, "ho_coverage_induced_rate") or 0) > 5.0 or (
                           _get(k, "target_rsrp") is not None and _get(k, "target_rsrp") < -110
                       ),
                       "Coverage-induced HO failure — weak serving or target cell at decision",
                       0.80, ["Close coverage gap on HO corridor", "Adjust A3/A5 thresholds", "Add filler cell"],
                       ["ho_coverage_induced_rate", "target_rsrp", "ss_rsrp"]),
        RuleDefinition("ho_interference_induced", cat, "Interference-induced HO failure",
                       lambda k: (_get(k, "ho_interference_induced_rate") or 0) > 4.0 or (
                           _get(k, "ss_sinr") is not None and _get(k, "ss_sinr") < 0
                           and (_get(k, "ho_success_rate") or 100) < 96
                       ),
                       "Interference-induced HO failure — low SINR destabilizes mobility",
                       0.77, ["PCI/ICIC review", "External interference hunt", "Verify SSB SINR at edge"],
                       ["ho_interference_induced_rate", "ss_sinr"]),
        RuleDefinition("ho_beam_instability", cat, "Beam instability at HO",
                       lambda k: (_get(k, "ho_beam_instability_rate") or 0) > 3.0,
                       "Beam instability during HO — SSB beam switch stress at sector edge",
                       0.74, ["Review SSB beam set", "Validate beam correspondence with neighbor", "Check CSI-RS config"],
                       ["ho_beam_instability_rate"]),
        RuleDefinition("ho_mobility_config", cat, "Mobility configuration issue",
                       lambda k: (_get(k, "ho_mobility_config_rate") or 0) > 8.0,
                       "Mobility parameter mis-tuning — too early/late HO or ping-pong pattern",
                       0.75, ["Audit A3 offset and hysteresis", "Review time-to-trigger", "Tune CIO between pair"],
                       ["ho_mobility_config_rate", "ho_too_early_rate", "ho_too_late_rate", "ho_ping_pong_rate"]),
        RuleDefinition("ho_xn_transport", cat, "Xn transport HO degradation",
                       lambda k: (_get(k, "ho_xn_transport_rate") or 0) > 2.0 or (
                           _get(k, "ho_mean_xn_latency_ms") is not None and _get(k, "ho_mean_xn_latency_ms") > 80
                       ),
                       "Xn transport latency or loss impacting HO preparation",
                       0.79, ["Check Xn IPsec/SCTP", "Review packet loss on fronthaul/backhaul", "Validate Xn neighbor"],
                       ["ho_xn_transport_rate", "ho_mean_xn_latency_ms", "ho_mean_packet_loss_pct"]),
        RuleDefinition("ho_missing_neighbor_enriched", cat, "Missing neighbor (enriched)",
                       lambda k: (_get(k, "ho_missing_neighbor_rate") or 0) > 2.0,
                       "HO to missing or inactive neighbor relation — prep failure likely",
                       0.82, ["Add NCR via ANR", "Validate neighbor allow-list", "Run NCL audit"],
                       ["ho_missing_neighbor_rate", "nr_neighbor_count"]),
    ]


HO_RULE_ENGINE = RuleEngine("handover", _ho_rules())
