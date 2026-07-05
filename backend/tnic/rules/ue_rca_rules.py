"""UE protocol RCA rules — failure scenario definitions and recommendations."""

from __future__ import annotations

from typing import Any

from tnic.parsers.ue_trace_parser import UETraceEvent

# Failure scenario → metadata
UE_FAILURE_SCENARIOS: dict[str, dict[str, Any]] = {
    "MIB_DECODE_FAILURE": {
        "issue": "MIB Decode Failure",
        "failure_stage": "PHY/MIB decode",
        "protocol_layer": "PHY",
        "primary_causes": {"LOW_SINR": "RF interference — SINR too low for PBCH/MIB", "DEFAULT": "PBCH/MIB decode failed at cell edge"},
        "recommendations": ["Check SS-RSRP/SINR at failure geo", "Audit PCI/interference", "Verify beam coverage"],
        "correlate_agents": ["rf_coverage", "beamforming", "gnb_syslog"],
    },
    "SIB_ACQUISITION_FAILURE": {
        "issue": "SIB Acquisition Failure",
        "failure_stage": "SIB1/SI decode",
        "protocol_layer": "SIB",
        "primary_causes": {"DEFAULT": "SIB1 not decoded — cell barred or weak coverage"},
        "recommendations": ["Verify SIB1 broadcast schedule", "Check cell barring", "Improve coverage at access point"],
        "correlate_agents": ["rf_coverage", "rach", "config_audit"],
    },
    "RACH_FAILURE": {
        "issue": "RACH Failure",
        "failure_stage": "RACH MSG1-MSG4",
        "protocol_layer": "RACH",
        "primary_causes": {
            "NO_RAR_RESPONSE": "No RAR — MSG1 not detected or PRACH collision",
            "DEFAULT": "Random access procedure failed",
        },
        "recommendations": ["Audit PRACH config and root sequence", "Check UL interference", "Review RACH occasion density"],
        "correlate_agents": ["rach", "gnb_syslog", "rf_coverage", "config_audit"],
    },
    "RRC_SETUP_FAILURE": {
        "issue": "RRC Setup Failure",
        "failure_stage": "RRC Setup Request/Complete",
        "protocol_layer": "RRC",
        "primary_causes": {
            "CELL_CONGESTION": "Cell admission control / congestion",
            "DEFAULT": "RRC setup rejected or timed out",
        },
        "recommendations": ["Check cell load and barring", "Verify AMF N2 reachability", "Review admission control params"],
        "correlate_agents": ["rach", "core", "gnb_syslog"],
    },
    "AUTHENTICATION_FAILURE": {
        "issue": "Authentication Failure",
        "failure_stage": "NAS Authentication",
        "protocol_layer": "NAS",
        "primary_causes": {"AUTH_TIMEOUT": "Authentication timeout — AUSF/UDM path", "DEFAULT": "NAS authentication failed"},
        "recommendations": ["Check AUSF/UDM logs", "Verify SIM/subscription profile", "Inspect NAS cause code"],
        "correlate_agents": ["core", "config_audit"],
    },
    "REGISTRATION_FAILURE": {
        "issue": "Registration Failure",
        "failure_stage": "NAS Registration",
        "protocol_layer": "NAS",
        "primary_causes": {"TA_NOT_ALLOWED": "Tracking area not allowed", "DEFAULT": "5GMM registration rejected"},
        "recommendations": ["Verify TA/PLMN config", "Check AMF registration area", "Audit slice/DNN subscription"],
        "correlate_agents": ["core", "config_audit"],
    },
    "PAGING_FAILURE": {
        "issue": "Paging Failure",
        "failure_stage": "Paging Response",
        "protocol_layer": "Paging",
        "primary_causes": {"T3417_EXPIRY": "T3417 expiry — UE did not respond to page", "DEFAULT": "Paging response failure"},
        "recommendations": ["Check DRX/paging cycle alignment", "Verify TAC/paging area", "Review coverage during idle"],
        "correlate_agents": ["rf_coverage", "rach"],
    },
    "HO_FAILURE": {
        "issue": "HO Failure",
        "failure_stage": "Mobility HO Request/Complete",
        "protocol_layer": "Mobility",
        "primary_causes": {
            "HO_PREP_FAILURE": "HO preparation failed — target not ready",
            "DEFAULT": "Handover procedure failed",
        },
        "recommendations": ["Verify neighbor relation and Xn/NG", "Check target cell RF", "Review A3/TTT mobility params"],
        "correlate_agents": ["handover", "gnb_syslog", "anr", "config_audit"],
    },
    "PING_PONG_HO": {
        "issue": "Ping Pong HO",
        "failure_stage": "Mobility ping-pong",
        "protocol_layer": "Mobility",
        "primary_causes": {"PING_PONG_HO": "UE returned to source — hysteresis mis-tuned", "DEFAULT": "Repeated HO between neighbors"},
        "recommendations": ["Increase hysteresis/CIO", "Fix overshoot/overlap geometry", "Review time-to-trigger"],
        "correlate_agents": ["handover", "config_audit", "rf_coverage"],
    },
    "TOO_EARLY_HO": {
        "issue": "Too Early HO",
        "failure_stage": "Mobility too-early",
        "protocol_layer": "Mobility",
        "primary_causes": {"DEFAULT": "HO triggered before UE reached cell edge"},
        "recommendations": ["Increase A3 offset/TTT", "Reduce serving cell overshoot"],
        "correlate_agents": ["handover", "config_audit"],
    },
    "TOO_LATE_HO": {
        "issue": "Too Late HO",
        "failure_stage": "Mobility too-late",
        "protocol_layer": "Mobility",
        "primary_causes": {"DEFAULT": "HO triggered after UE at cell edge"},
        "recommendations": ["Decrease A3 offset", "Add filler cell on corridor"],
        "correlate_agents": ["handover", "rlf", "rf_coverage"],
    },
    "T310_EXPIRY": {
        "issue": "T310 Expiry",
        "failure_stage": "RLF T310 timer",
        "protocol_layer": "RLF",
        "primary_causes": {"COVERAGE_HOLE": "Out-of-sync at coverage hole", "DEFAULT": "T310 expired — radio link degraded"},
        "recommendations": ["Map RLF geography vs RSRP", "Close coverage gap", "Check interference at failure point"],
        "correlate_agents": ["rlf", "rf_coverage", "gnb_syslog"],
    },
    "RADIO_LINK_FAILURE": {
        "issue": "Radio Link Failure",
        "failure_stage": "RLF out-of-sync",
        "protocol_layer": "RLF",
        "primary_causes": {"DEFAULT": "Radio link failure — sync lost"},
        "recommendations": ["Correlate with RSRP/SINR at failure", "Review N310/T310 config"],
        "correlate_agents": ["rlf", "rf_coverage", "gnb_syslog"],
    },
    "RE_ESTABLISHMENT_FAILURE": {
        "issue": "Re-establishment Failure",
        "failure_stage": "RRC Re-establishment",
        "protocol_layer": "RRC",
        "primary_causes": {"DEFAULT": "RRC re-establishment failed after RLF"},
        "recommendations": ["Verify re-establishment cell selection", "Check coverage on candidate cells"],
        "correlate_agents": ["rlf", "rach", "rf_coverage"],
    },
    "COVERAGE_HOLE": {
        "issue": "Coverage Hole",
        "failure_stage": "RF coverage",
        "protocol_layer": "PHY",
        "primary_causes": {"COVERAGE_HOLE": "UE in coverage hole at failure point", "DEFAULT": "Weak RF coverage"},
        "recommendations": ["Retilt or add filler cell", "Re-drive cluster geography"],
        "correlate_agents": ["rf_coverage", "beamforming"],
    },
    "INTERFERENCE": {
        "issue": "Interference",
        "failure_stage": "RF SINR collapse",
        "protocol_layer": "PHY",
        "primary_causes": {"LOW_SINR": "Low SINR — co-channel interference", "DEFAULT": "Interference-limited decode"},
        "recommendations": ["Run PCI/mod-3 scan", "Identify dominant interferer"],
        "correlate_agents": ["rf_coverage", "anr"],
    },
    "PDU_SESSION_FAILURE": {
        "issue": "PDU Session Failure",
        "failure_stage": "5GSM PDU session establishment",
        "protocol_layer": "5GSM",
        "primary_causes": {"DEFAULT": "PDU session setup rejected"},
        "recommendations": ["Inspect SMF session logs", "Verify DNN/slice/QoS template"],
        "correlate_agents": ["core", "vonr", "config_audit"],
    },
    "QOS_FLOW_FAILURE": {
        "issue": "QoS Flow Failure",
        "failure_stage": "5GSM QoS flow setup",
        "protocol_layer": "5GSM",
        "primary_causes": {"QFI_MAPPING_ERROR": "QFI mapping error on SMF/UPF", "DEFAULT": "QoS flow setup failed"},
        "recommendations": ["Audit 5QI/QFI profile", "Verify UPF QoS mapping"],
        "correlate_agents": ["vonr", "core", "config_audit"],
    },
    "DRB_SETUP_FAILURE": {
        "issue": "DRB Setup Failure",
        "failure_stage": "RRC DRB establishment",
        "protocol_layer": "RRC",
        "primary_causes": {
            "RADIO_RESOURCE_UNAVAILABLE": "No radio resources for DRB",
            "DEFAULT": "DRB setup failed",
        },
        "recommendations": ["Check PRB scheduler load", "Review DRB/QoS admission", "Offload congested cell"],
        "correlate_agents": ["throughput", "beamforming", "rf_coverage"],
    },
    "BEAM_INSTABILITY": {
        "issue": "Beam Instability",
        "failure_stage": "Beam management",
        "protocol_layer": "BEAM",
        "primary_causes": {"EXCESSIVE_SWITCHING": "Excessive beam switching", "DEFAULT": "Beam instability detected"},
        "recommendations": ["Tune beam management timers", "Recalibrate MIMO array"],
        "correlate_agents": ["beamforming", "rf_coverage", "gnb_syslog"],
    },
    "VONR_DROP": {
        "issue": "VoNR Drop",
        "failure_stage": "IMS/VoNR bearer",
        "protocol_layer": "IMS",
        "primary_causes": {"IMS_TIMEOUT": "IMS/SIP timeout on voice path", "DEFAULT": "VoNR call dropped"},
        "recommendations": ["Trace SIP/RTP path", "Check 5QI-1 scheduler", "Improve NR voice coverage"],
        "correlate_agents": ["vonr", "transport", "rf_coverage"],
    },
    "IMS_FAILURE": {
        "issue": "IMS Failure",
        "failure_stage": "IMS/SIP",
        "protocol_layer": "IMS",
        "primary_causes": {"IMS_TIMEOUT": "SIP timeout — P-CSCF/SBC path", "DEFAULT": "IMS registration or SIP failure"},
        "recommendations": ["Check IMS core reachability", "Verify P-CSCF/SBC", "Audit QoS end-to-end for 5QI-1"],
        "correlate_agents": ["vonr", "transport", "core"],
    },
}


def resolve_scenario(event: UETraceEvent) -> str:
    key = event.scenario_key()
    return key or "UNKNOWN_FAILURE"


def build_ue_rca_from_event(event: UETraceEvent) -> dict[str, Any]:
    scenario_key = resolve_scenario(event)
    spec = UE_FAILURE_SCENARIOS.get(scenario_key, {
        "issue": scenario_key.replace("_", " ").title(),
        "failure_stage": f"{event.layer}/{event.procedure}",
        "protocol_layer": event.layer,
        "primary_causes": {"DEFAULT": event.cause or event.message},
        "recommendations": ["Investigate UE trace at failure timestamp"],
        "correlate_agents": ["gnb_syslog"],
    })
    cause = event.cause or "DEFAULT"
    primary = spec["primary_causes"].get(cause, spec["primary_causes"].get("DEFAULT", event.message))
    return {
        "scenario_key": scenario_key,
        "issue": spec["issue"],
        "failure_stage": spec["failure_stage"],
        "protocol_layer": spec["protocol_layer"],
        "primary_root_cause": primary,
        "secondary_root_cause": event.cause if event.cause and event.cause != cause else "",
        "recommendations": list(spec["recommendations"]),
        "correlate_agents": list(spec["correlate_agents"]),
        "evidence": [
            f"UE {event.ue_id} @ {event.timestamp}",
            f"{event.layer}/{event.procedure}/{event.message} → {event.result}",
            f"Cause: {event.cause}" if event.cause else f"Message: {event.message}",
        ],
    }
