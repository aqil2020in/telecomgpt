"""Telecom-grade RCA catalog — 28 NOC/Optimization RCA workflows."""

from __future__ import annotations

from typing import Any

# Network domains: Coverage, Mobility, Accessibility, Retainability, Throughput,
# VoNR, Transport, Core, Beamforming, Configuration, PM, Alarm, Syslog

RCA_CATALOG: dict[str, dict[str, Any]] = {
    "coverage_hole": {
        "title": "Coverage Hole RCA",
        "domains": ["Coverage"],
        "agents": ["rf_coverage", "rlf", "rach", "handover", "throughput", "vonr"],
        "rule_ids": ["cov_coverage_hole", "rlf_coverage_hole", "rf_coverage_primary"],
        "pm_counters": ["ss_rsrp", "rlf_rate", "rlf_coverage_pct", "rach_success_rate"],
        "syslog_signatures": [],
        "config_validations": ["ssb_periodicity", "beam_tilt"],
        "recommended_fixes": [
            "Retilt AAU or add filler/small cell",
            "Increase reference signal power within license limits",
            "Re-drive cluster to validate hole geography",
        ],
        "keywords": ("coverage hole", "dead zone", "no service", "rsrp -11"),
    },
    "overshooting_cell": {
        "title": "Overshooting Cell RCA",
        "domains": ["Coverage", "Mobility"],
        "agents": ["rf_coverage", "handover", "anr", "config_audit"],
        "rule_ids": ["cov_overshooting", "ho_too_early", "ho_ping_pong"],
        "pm_counters": ["ss_rsrp", "distance_miles", "ho_too_early_rate", "target_rsrp"],
        "syslog_signatures": [],
        "config_validations": ["ho_a3_offset_db", "ho_ttt_ms", "ho_hysteresis_db"],
        "recommended_fixes": [
            "Reduce electrical tilt / power to shrink footprint",
            "Tune A3 offset and TTT to reduce too-early HO",
            "Add intermediate cell on overshoot corridor",
        ],
        "keywords": ("overshoot", "overshooting", "extended coverage", "far cell"),
    },
    "pilot_pollution": {
        "title": "Pilot Pollution RCA",
        "domains": ["Coverage", "Mobility"],
        "agents": ["rf_coverage", "handover", "anr", "beamforming"],
        "rule_ids": ["cov_pilot_pollution", "ho_wrong_cell", "anr_pci_conflict"],
        "pm_counters": ["ss_rsrp", "ss_sinr", "pilot_pollution_index", "ho_wrong_cell_rate"],
        "syslog_signatures": ["syslog_pci_conflict"],
        "config_validations": ["pci", "pci_mod3_collision"],
        "recommended_fixes": [
            "PCI replan to reduce co-channel confusion",
            "Adjust CIO between dominant pilot pair",
            "Reduce overlap via tilt/azimuth optimization",
        ],
        "keywords": ("pilot pollution", "dominant pilot", "equal rsrp", "pilot confusion"),
    },
    "interference": {
        "title": "Interference RCA",
        "domains": ["Coverage", "Throughput"],
        "agents": ["rf_coverage", "rlf", "throughput", "anr"],
        "rule_ids": ["cov_interference", "rlf_interference", "tput_low_cqi_bler"],
        "pm_counters": ["ss_sinr", "ss_rsrp", "bler", "rlf_interference_pct"],
        "syslog_signatures": ["syslog_pci_conflict"],
        "config_validations": ["pci", "prach_root_sequence"],
        "recommended_fixes": [
            "Run PCI/mod-3 interference scan",
            "Identify external jammer or adjacent-sector leak",
            "Adjust beam overlap and downtilt",
        ],
        "keywords": ("interference", "co-channel", "mod-3", "sinr collapse"),
    },
    "ho_prep_failure": {
        "title": "HO Prep Failure RCA",
        "domains": ["Mobility", "Transport"],
        "agents": ["handover", "anr", "transport", "gnb_syslog", "config_audit"],
        "rule_ids": ["ho_prep_failure", "ho_missing_neighbor", "anr_ho_nbr_mismatch"],
        "pm_counters": ["ho_prep_fail_rate", "ho_xn_fail_rate", "nr_neighbor_count"],
        "syslog_signatures": ["syslog_ngap_ho_failure", "syslog_xnap_failure"],
        "config_validations": ["ho_a3_offset_db", "xn_neighbor"],
        "recommended_fixes": [
            "Verify target cell readiness and NCL entry",
            "Check Xn/NG transport and SCTP",
            "Add missing neighbor via ANR",
        ],
        "keywords": ("ho prep", "preparation failure", "prep fail", "handover prep"),
    },
    "ho_execution_failure": {
        "title": "HO Execution Failure RCA",
        "domains": ["Mobility", "Coverage"],
        "agents": ["handover", "rf_coverage", "rlf"],
        "rule_ids": ["ho_execution_failure", "ho_weak_target_rf", "rlf_after_ho"],
        "pm_counters": ["ho_exec_fail_rate", "ho_success_rate", "target_rsrp"],
        "syslog_signatures": ["syslog_ngap_ho_failure"],
        "config_validations": ["ho_a3_offset_db", "ho_a5_threshold"],
        "recommended_fixes": [
            "Compare source/target RSRP at HO decision",
            "Audit A3/A5 mobility parameters",
            "Drive-test HO corridor for RF gap",
        ],
        "keywords": ("ho exec", "execution failure", "ho execution", "handover execution"),
    },
    "ping_pong": {
        "title": "Ping Pong HO RCA",
        "domains": ["Mobility", "Coverage"],
        "agents": ["handover", "config_audit", "anr"],
        "rule_ids": ["ho_ping_pong", "cov_overshooting"],
        "pm_counters": ["ho_ping_pong_rate", "ho_too_early_rate", "ho_too_late_rate"],
        "syslog_signatures": [],
        "config_validations": ["ho_hysteresis_db", "ho_a3_offset_db", "cell_individual_offset"],
        "recommended_fixes": [
            "Increase hysteresis between neighbor pair",
            "Review CIO and time-to-trigger",
            "Fix overshoot/overlap geometry",
        ],
        "keywords": ("ping pong", "ping-pong", "ho bounce", "repeated handover"),
    },
    "too_early_ho": {
        "title": "Too Early HO RCA",
        "domains": ["Mobility", "Coverage"],
        "agents": ["handover", "config_audit", "rf_coverage"],
        "rule_ids": ["ho_too_early", "cov_overshooting"],
        "pm_counters": ["ho_too_early_rate", "ss_rsrp", "target_rsrp"],
        "syslog_signatures": [],
        "config_validations": ["ho_a3_offset_db", "ho_ttt_ms"],
        "recommended_fixes": [
            "Increase A3 offset or time-to-trigger",
            "Reduce serving cell overshoot",
            "Review cell individual offsets",
        ],
        "keywords": ("too early", "early ho", "premature handover"),
    },
    "too_late_ho": {
        "title": "Too Late HO RCA",
        "domains": ["Mobility", "Coverage", "Retainability"],
        "agents": ["handover", "rlf", "rf_coverage"],
        "rule_ids": ["ho_too_late", "rlf_coverage_hole", "ho_weak_target_rf"],
        "pm_counters": ["ho_too_late_rate", "rlf_rate", "ss_rsrp"],
        "syslog_signatures": ["syslog_rlf_out_of_sync"],
        "config_validations": ["ho_a3_offset_db", "ho_ttt_ms"],
        "recommended_fixes": [
            "Decrease A3 offset / TTT",
            "Add filler cell on HO corridor",
            "Close coverage gap at cell edge",
        ],
        "keywords": ("too late", "late ho", "delayed handover"),
    },
    "rlf": {
        "title": "RLF RCA",
        "domains": ["Retainability", "Coverage", "Mobility"],
        "agents": ["rlf", "rf_coverage", "handover", "gnb_syslog"],
        "rule_ids": ["rlf_coverage_hole", "rlf_interference", "rlf_t310_n310", "rlf_after_ho"],
        "pm_counters": ["rlf_rate", "rlf_coverage_pct", "rlf_interference_pct", "out_of_sync_events"],
        "syslog_signatures": ["syslog_rlf_out_of_sync"],
        "config_validations": ["n310", "n311", "t310"],
        "recommended_fixes": [
            "Map RLF cluster geography vs RSRP/SINR",
            "Fix root cause: coverage, interference, or post-HO target",
            "Review sync timer configuration",
        ],
        "keywords": ("rlf", "radio link failure", "out of sync", "t310", "n310"),
    },
    "rrc_setup_failure": {
        "title": "RRC Setup Failure RCA",
        "domains": ["Accessibility", "Core"],
        "agents": ["rach", "core", "config_audit", "gnb_syslog"],
        "rule_ids": ["rach_rrc_setup_fail", "core_ng_n2_failure"],
        "pm_counters": ["rrc_setup_fail_rate", "rach_success_rate"],
        "syslog_signatures": ["syslog_rrc_reject"],
        "config_validations": ["sib1", "cell_barring"],
        "recommended_fixes": [
            "Check SIB1 broadcast and cell barring",
            "Verify AMF N2 reachability",
            "Review load and admission control",
        ],
        "keywords": ("rrc setup", "rrc fail", "rrc failure", "rrc reject"),
    },
    "rach_failure": {
        "title": "RACH Failure RCA",
        "domains": ["Accessibility", "Coverage"],
        "agents": ["rach", "rf_coverage", "config_audit", "gnb_syslog"],
        "rule_ids": ["rach_msg1_fail", "rach_msg3_fail", "rach_low_success", "rach_prach_config"],
        "pm_counters": ["rach_success_rate", "rach_msg1_fail_rate", "rach_msg3_fail_rate"],
        "syslog_signatures": ["syslog_rach_preamble_collision"],
        "config_validations": ["prach_root_sequence", "prach_configuration_index"],
        "recommended_fixes": [
            "Audit PRACH root sequence and occasion density",
            "Check UL interference on PRACH REs",
            "Review power ramping and preamble format",
        ],
        "keywords": ("rach fail", "rach failure", "prach", "msg1", "msg3", "random access"),
    },
    "vonr_drop": {
        "title": "VoNR Drop RCA",
        "domains": ["VoNR", "Retainability", "Coverage"],
        "agents": ["vonr", "call_drop", "rf_coverage", "handover"],
        "rule_ids": ["vonr_drop", "vonr_coverage_hole", "drop_ims"],
        "pm_counters": ["vonr_drop_rate", "drop_ims_pct", "vonr_setup_success_rate"],
        "syslog_signatures": ["syslog_vonr_qfi_setup_fail"],
        "config_validations": ["5qi_profile", "ims_dnn"],
        "recommended_fixes": [
            "Improve NR edge coverage for 5QI-1",
            "Check IMS bearer stability during mobility",
            "Enable EPS fallback if NR voice unsustainable",
        ],
        "keywords": ("vonr drop", "voice drop", "volte drop", "ims drop", "5qi-1 drop"),
    },
    "pdu_session_failure": {
        "title": "PDU Session Failure RCA",
        "domains": ["Core", "VoNR"],
        "agents": ["core", "vonr", "gnb_syslog"],
        "rule_ids": ["core_pdu_session_fail", "vonr_amf_smf_session"],
        "pm_counters": ["pdu_session_fail_rate", "amf_release_rate"],
        "syslog_signatures": ["syslog_amf_release", "syslog_vonr_qfi_setup_fail"],
        "config_validations": ["5qi_profile", "dnn", "slice_sst"],
        "recommended_fixes": [
            "Inspect SMF session management logs",
            "Verify slice/DNN and QoS flow templates",
            "Check AMF 5GMM cause codes",
        ],
        "keywords": ("pdu session", "session fail", "smf fail", "session setup fail"),
    },
    "beam_failure": {
        "title": "Beam Failure RCA",
        "domains": ["Beamforming", "Coverage", "Throughput"],
        "agents": ["beamforming", "rf_coverage", "throughput"],
        "rule_ids": ["beam_failure", "beam_instability", "beam_coverage_gap"],
        "pm_counters": ["beam_failure_ratio", "beam_switch_rate", "beam_health_score"],
        "syslog_signatures": [],
        "config_validations": ["ssb_beam_count", "beam_tilt"],
        "recommended_fixes": [
            "Recalibrate massive MIMO array",
            "Tune beam management timers and SSB hysteresis",
            "Optimize per-beam tilt/azimuth",
        ],
        "keywords": ("beam fail", "beam failure", "ssb fail", "beam switch", "mimo beam"),
    },
    "low_throughput": {
        "title": "Low Throughput RCA",
        "domains": ["Throughput", "Coverage", "Beamforming"],
        "agents": ["throughput", "beamforming", "rf_coverage", "transport"],
        "rule_ids": ["tput_low_cqi_bler", "tput_low_mcs", "tput_stuck_rank1"],
        "pm_counters": ["throughput_mbps", "cqi", "bler", "mcs", "ri"],
        "syslog_signatures": ["syslog_pdcp_discard"],
        "config_validations": ["scheduler_policy", "mimo_mode"],
        "recommended_fixes": [
            "Improve SINR/CQI at serving location",
            "Check MIMO rank and MCS distribution",
            "Rule out transport bottleneck",
        ],
        "keywords": ("low throughput", "dl tp", "throughput degradation", "slow speed"),
    },
    "latency": {
        "title": "Latency RCA",
        "domains": ["Throughput", "Transport", "Core"],
        "agents": ["latency", "transport", "core"],
        "rule_ids": ["lat_upf", "lat_xn", "lat_cudu"],
        "pm_counters": ["latency_ms", "upf_latency_ms", "xn_latency_ms"],
        "syslog_signatures": ["syslog_transport_loss"],
        "config_validations": ["drx_cycle", "5qi_delay_budget"],
        "recommended_fixes": [
            "Segment latency: RAN vs transport vs UPF",
            "Check DRX and scheduler delay",
            "Scale UPF or optimize N3 path",
        ],
        "keywords": ("latency", "rtt", "delay", "high ping", "upf latency"),
    },
    "anr_failure": {
        "title": "ANR Failure RCA",
        "domains": ["Mobility", "Configuration"],
        "agents": ["anr", "handover", "config_audit"],
        "rule_ids": ["anr_stale_neighbor", "anr_ho_nbr_mismatch", "anr_prach_conflict"],
        "pm_counters": ["anr_blacklist_count", "stale_neighbor_pct", "nr_neighbor_count"],
        "syslog_signatures": ["syslog_pci_conflict"],
        "config_validations": ["anr_policy", "nbr_allow_list"],
        "recommended_fixes": [
            "Clear ANR blacklist after root-cause fix",
            "Re-run ANR discovery on affected band",
            "Validate ANR add/remove thresholds",
        ],
        "keywords": ("anr fail", "anr failure", "neighbor relation", "anr blacklist"),
    },
    "neighbor_missing": {
        "title": "Neighbor Missing RCA",
        "domains": ["Mobility", "Configuration"],
        "agents": ["anr", "handover", "config_audit"],
        "rule_ids": ["anr_missing_neighbor", "ho_missing_neighbor"],
        "pm_counters": ["nr_neighbor_count", "ho_prep_fail_rate"],
        "syslog_signatures": [],
        "config_validations": ["nbr_allow_list", "anr_policy"],
        "recommended_fixes": [
            "Enable ANR add or manually create NCR",
            "Validate intra/inter-frequency neighbor policy",
            "Drive-test to confirm missing overlap pair",
        ],
        "keywords": ("missing neighbor", "no neighbor", "undefined target", "ncr missing"),
    },
    "pci_conflict": {
        "title": "PCI Conflict RCA",
        "domains": ["Coverage", "Mobility", "Configuration"],
        "agents": ["anr", "handover", "config_audit"],
        "rule_ids": ["anr_pci_conflict", "ho_pci_collision"],
        "pm_counters": ["pci_conflict_count", "pci_mod3_collision", "ho_wrong_cell_rate"],
        "syslog_signatures": ["syslog_pci_conflict"],
        "config_validations": ["pci", "pci_plan"],
        "recommended_fixes": [
            "Run PCI audit and replan conflicting pair",
            "Enable ANR PCI optimization",
            "Update neighbor PCI in NCL",
        ],
        "keywords": ("pci conflict", "pci collision", "pci confusion", "mod-3 collision"),
    },
    "configuration_drift": {
        "title": "Configuration Drift RCA",
        "domains": ["Configuration"],
        "agents": ["config_audit", "handover", "rach", "vonr"],
        "rule_ids": ["cfg_audit_ho_a3_offset_db", "cfg_audit_prach_root_sequence", "cfg_audit_5qi_profile"],
        "pm_counters": [],
        "syslog_signatures": [],
        "config_validations": ["ho_a3_offset_db", "ho_ttt_ms", "prach_root_sequence", "5qi_profile", "pci"],
        "recommended_fixes": [
            "Compare live CM vs golden baseline JSON",
            "Rollback recent parameter changes",
            "Enable CM change audit trail",
        ],
        "keywords": ("config drift", "parameter drift", "cm audit", "golden config", "misconfiguration"),
    },
    "scheduler_congestion": {
        "title": "Scheduler Congestion RCA",
        "domains": ["Throughput"],
        "agents": ["throughput", "beamforming", "handover"],
        "rule_ids": ["tput_congestion", "tput_prb_congestion_80", "beam_overload"],
        "pm_counters": ["prb_utilization", "throughput_mbps", "beam_load_pct"],
        "syslog_signatures": [],
        "config_validations": ["scheduler_policy", "load_balancing"],
        "recommended_fixes": [
            "Offload traffic via HO or CA",
            "Add carrier or small cell capacity",
            "Rebalance beam/PRB scheduler weights",
        ],
        "keywords": ("scheduler", "prb congestion", "prb util", "resource congestion"),
    },
    "transport_congestion": {
        "title": "Transport Congestion RCA",
        "domains": ["Transport", "Throughput"],
        "agents": ["transport", "throughput", "latency"],
        "rule_ids": ["transport_congestion", "transport_backhaul", "tput_backhaul"],
        "pm_counters": ["backhaul_utilization", "transport_loss_rate", "n3_utilization"],
        "syslog_signatures": ["syslog_transport_loss"],
        "config_validations": ["qos_n3", "gtp_mtu"],
        "recommended_fixes": [
            "Upgrade N3/F1/backhaul link capacity",
            "Enable QoS on transport path",
            "Check switch/router queue drops",
        ],
        "keywords": ("transport congestion", "backhaul", "n3 congestion", "fronthaul"),
    },
    "xn_failure": {
        "title": "Xn Failure RCA",
        "domains": ["Mobility", "Transport"],
        "agents": ["handover", "transport", "gnb_syslog"],
        "rule_ids": ["ho_xn_failure", "transport_xn_sctp"],
        "pm_counters": ["ho_xn_fail_rate", "xn_latency_ms"],
        "syslog_signatures": ["syslog_xnap_failure"],
        "config_validations": ["xn_neighbor", "sctp_profile"],
        "recommended_fixes": [
            "Verify Xn SCTP/IPsec connectivity",
            "Check Xn neighbor relation and gNB IDs",
            "Review XnAP cause codes in syslog",
        ],
        "keywords": ("xn fail", "xnap", "xn interface", "sctp xn"),
    },
    "ng_n2_failure": {
        "title": "NG/N2 Failure RCA",
        "domains": ["Core", "Mobility"],
        "agents": ["core", "handover", "gnb_syslog"],
        "rule_ids": ["core_ng_n2_failure", "ho_n2_failure"],
        "pm_counters": ["ho_n2_fail_rate", "amf_release_rate", "ngap_failure_count"],
        "syslog_signatures": ["syslog_ngap_ho_failure", "syslog_amf_release"],
        "config_validations": ["amf_pool", "ngap_timers"],
        "recommended_fixes": [
            "Check AMF load and NGAP timer configuration",
            "Verify N2 SCTP between gNB and AMF",
            "Inspect NGAP HandoverFailure / UEContextRelease cause",
        ],
        "keywords": ("ng fail", "n2 fail", "ngap", "amf fail", "n2 interface"),
    },
    "pm_counter_integrity": {
        "title": "PM Counter Integrity Validation",
        "domains": ["Configuration"],
        "agents": ["pm"],
        "rule_ids": ["pm_ho_rate_mismatch", "pm_cqi_range", "pm_bler_unit", "pm_rsrp_unit"],
        "pm_counters": ["ho_success_rate", "ho_prep_fail_rate", "cqi", "bler", "ss_rsrp"],
        "syslog_signatures": [],
        "config_validations": ["kpi_formula", "counter_definition"],
        "recommended_fixes": [
            "Reconcile PM counter definitions with vendor MO",
            "Normalize ratio vs percentage counters",
            "Validate KPI derivation formulas",
        ],
        "keywords": ("pm validation", "counter integrity", "kpi mismatch", "counter definition"),
    },
    "alarm_correlation": {
        "title": "Alarm Correlation RCA",
        "domains": ["Coverage", "Transport", "Core"],
        "agents": ["gnb_syslog", "transport", "core", "pm"],
        "rule_ids": ["alarm_critical_active", "alarm_transport_link", "alarm_du_cu"],
        "pm_counters": ["active_alarm_count", "critical_alarm_count"],
        "syslog_signatures": ["syslog_du_crash", "syslog_transport_loss"],
        "config_validations": [],
        "recommended_fixes": [
            "Correlate FM alarm timeline with KPI degradation",
            "Clear root HW/transport alarm before RF optimization",
            "Escalate critical DU/CU/F1 alarms",
        ],
        "keywords": ("alarm", "fm alarm", "critical alarm", "alarm correlation"),
    },
    "syslog_correlation": {
        "title": "Syslog Correlation RCA",
        "domains": ["Mobility", "Retainability", "Accessibility", "Core"],
        "agents": ["gnb_syslog", "handover", "rlf", "rach", "core"],
        "rule_ids": [
            "syslog_ngap_ho_failure", "syslog_xnap_failure", "syslog_rlf_out_of_sync",
            "syslog_rach_preamble_collision", "syslog_amf_release",
        ],
        "pm_counters": [],
        "syslog_signatures": [
            "syslog_ngap_ho_failure", "syslog_xnap_failure", "syslog_rlf_out_of_sync",
            "syslog_rach_preamble_collision", "syslog_rrc_reject", "syslog_vonr_qfi_setup_fail",
            "syslog_amf_release", "syslog_du_crash", "syslog_transport_loss", "syslog_pci_conflict",
        ],
        "config_validations": [],
        "recommended_fixes": [
            "Parse gNB DU/CU syslog for signature match",
            "Cross-reference syslog timestamp with PM spike",
            "Attach log excerpt to RCA ticket",
        ],
        "keywords": ("syslog", "gnb log", "log correlation", "du log", "cu log"),
    },
}


def detect_rca_type(query: str, explicit: str | None = None) -> str | None:
    """Detect RCA catalog key from query or explicit type."""
    if explicit and explicit.lower().replace(" ", "_") in RCA_CATALOG:
        return explicit.lower().replace(" ", "_")
    if explicit and explicit in RCA_CATALOG:
        return explicit
    ql = query.lower()
    scores = {k: sum(1 for kw in v.get("keywords", ()) if kw in ql) for k, v in RCA_CATALOG.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None


def rca_agents(rca_key: str) -> list[str]:
    return RCA_CATALOG.get(rca_key, {}).get("agents", [])


def list_rca_types() -> list[dict[str, Any]]:
    """Return catalog summary for API/dashboard."""
    return [
        {
            "rca_type": key,
            "title": spec["title"],
            "domains": spec["domains"],
            "agents": spec["agents"],
            "rule_count": len(spec.get("rule_ids", [])),
        }
        for key, spec in RCA_CATALOG.items()
    ]
