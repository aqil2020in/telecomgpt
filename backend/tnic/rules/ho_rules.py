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
    ]


HO_RULE_ENGINE = RuleEngine("handover", _ho_rules())
