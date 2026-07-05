"""Industry RCA workflow registry — maps 4G/5G NOC workflows to TNIC agents."""

from __future__ import annotations

from typing import Any

# Domains: Coverage, Mobility, Accessibility, Retainability, Throughput, VoNR,
#          Transport, Core, Beamforming, Cell_Outage, Configuration

WORKFLOW_REGISTRY: dict[str, dict[str, Any]] = {
    "call_drop": {
        "title": "Call Drop Issue (4G/5G RAN)",
        "domains": ["Retainability", "Mobility", "Coverage", "Throughput", "Transport"],
        "agents": ["call_drop", "rlf", "handover", "rf_coverage", "throughput", "transport", "gnb_syslog"],
        "triggers": ["High DCR", "RRC re-establishment failure", "Drop events in logs"],
        "data_required": ["RRC counters", "HO success", "RLF logs", "UE traces", "RSRP maps"],
        "validation": ["RLF down", "DCR down", "HO SR up"],
        "pm_counters": [
            "call_drop_rate", "rlf_rate", "ho_success_rate", "drop_mobility_pct",
            "drop_radio_pct", "ss_rsrp", "ss_sinr",
        ],
        "syslog_signatures": ["syslog_rlf_out_of_sync", "syslog_pdcp_discard", "syslog_amf_release"],
    },
    "low_dl_throughput": {
        "title": "Low Downlink Throughput",
        "domains": ["Throughput", "Coverage", "Beamforming", "Transport"],
        "agents": ["throughput", "beamforming", "rf_coverage", "transport", "latency"],
        "triggers": ["DL TP below threshold", "User complaints", "Drive logs"],
        "data_required": ["PRB util", "CQI/MCS", "Transport latency", "TCP stats"],
        "validation": ["CQI/MCS up", "DL TP +20%"],
        "pm_counters": ["throughput_mbps", "cqi", "bler", "prb_utilization", "mcs", "backhaul_utilization"],
        "syslog_signatures": ["syslog_pdcp_discard"],
    },
    "low_ul_throughput": {
        "title": "Low Upload Throughput",
        "domains": ["Throughput", "Coverage"],
        "agents": ["throughput", "rf_coverage", "beamforming"],
        "triggers": ["High UL latency", "UL TP below threshold"],
        "data_required": ["PUSCH/PUCCH", "UL BLER", "UE PHR", "UL interference"],
        "validation": ["UL BLER down", "UL TP up"],
        "pm_counters": ["ul_throughput_mbps", "ul_bler_pct", "ue_power_headroom_db"],
        "syslog_signatures": [],
    },
    "volte_vonr_voice": {
        "title": "VoLTE / VoNR Call Drop / Mute",
        "domains": ["VoNR", "Core", "Coverage", "Mobility"],
        "agents": ["vonr", "call_drop", "core", "latency", "rf_coverage", "gnb_syslog"],
        "triggers": ["CSSR drop", "Voice mute", "IMS drops"],
        "data_required": ["SIP traces", "RTP flows", "IMS registration", "5QI-1 setup"],
        "validation": ["VoNR SR up", "MOS stable", "RTP loss down"],
        "pm_counters": ["vonr_setup_success_rate", "ims_registration_rate", "rtp_packet_loss_pct", "drop_ims_pct"],
        "syslog_signatures": ["syslog_vonr_qfi_setup_fail"],
    },
    "vonr_5g_sa": {
        "title": "VoNR Call Failure (5G SA)",
        "domains": ["VoNR", "Core", "Coverage"],
        "agents": ["vonr", "core", "rach", "rf_coverage", "config_audit"],
        "triggers": ["Low VoNR SR", "AMF/SMF setup failures"],
        "data_required": ["NAS logs", "AMF/SMF trace", "QoS flow setup", "IMS registration"],
        "validation": ["5QI-1 setup OK", "PDU session stable"],
        "pm_counters": ["vonr_setup_success_rate", "pdu_session_fail_rate", "amf_release_rate"],
        "syslog_signatures": ["syslog_vonr_qfi_setup_fail", "syslog_amf_release"],
    },
    "handover_failure": {
        "title": "Handover Failure (4G/5G)",
        "domains": ["Mobility", "Coverage", "Transport"],
        "agents": ["handover", "anr", "rf_coverage", "transport", "config_audit", "gnb_syslog"],
        "triggers": ["HO fail > 5%", "Mobility complaints"],
        "data_required": ["HO counters", "NCL", "A3/A2", "Drive logs", "Xn/NG traces"],
        "validation": ["HO SR restored", "Prep fail down"],
        "pm_counters": ["ho_success_rate", "ho_prep_fail_rate", "ho_xn_fail_rate", "target_rsrp"],
        "syslog_signatures": ["syslog_ngap_ho_failure", "syslog_xnap_failure"],
    },
    "rach_rrc_failure": {
        "title": "High RRC / RACH Connection Failure",
        "domains": ["Accessibility", "Coverage", "Core"],
        "agents": ["rach", "rf_coverage", "core", "config_audit", "gnb_syslog"],
        "triggers": ["RRC setup fail high", "Access issues"],
        "data_required": ["RRC setup counters", "RACH MSG1-4", "Load", "SIB"],
        "validation": ["RACH SR up", "RRC setup fail down"],
        "pm_counters": ["rach_success_rate", "rach_msg1_fail_rate", "rrc_setup_fail_rate"],
        "syslog_signatures": ["syslog_rach_preamble_collision", "syslog_rrc_reject"],
    },
    "cell_outage": {
        "title": "Cell Outage / Degraded Cell",
        "domains": ["Coverage", "Transport", "Core"],
        "agents": ["gnb_syslog", "pm", "transport", "config_audit", "rf_coverage"],
        "triggers": ["Cell down", "Sudden KPI degradation"],
        "data_required": ["FM alarms", "HW logs", "Transport status", "Power"],
        "validation": ["Cell availability up", "Alarms cleared"],
        "pm_counters": ["cell_availability", "transport_loss_rate"],
        "syslog_signatures": ["syslog_du_crash"],
    },
}


def detect_workflow(query: str) -> str | None:
    ql = query.lower()
    keys = {
        "call_drop": ("call drop", "dcr", "dropped call"),
        "low_dl_throughput": ("low throughput", "dl tp", "downlink throughput"),
        "low_ul_throughput": ("ul throughput", "upload throughput", "ul tp"),
        "volte_vonr_voice": ("volte", "mute", "voice drop", "ims drop"),
        "vonr_5g_sa": ("vonr", "5qi-1", "5qi 1", "voice bearer"),
        "handover_failure": ("handover fail", "ho fail", "ho failure", "mobility"),
        "rach_rrc_failure": ("rach fail", "rrc fail", "access fail", "prach"),
        "cell_outage": ("cell outage", "cell down", "degraded cell", "site down"),
    }
    scores = {k: sum(1 for kw in v if kw in ql) for k, v in keys.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None


def workflow_agents(workflow_key: str) -> list[str]:
    return WORKFLOW_REGISTRY.get(workflow_key, {}).get("agents", [])
