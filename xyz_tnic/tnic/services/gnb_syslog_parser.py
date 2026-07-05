"""gNB syslog signature parser — maps log lines to RCA findings."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SyslogSignature:
    sig_id: str
    pattern: re.Pattern[str]
    domain: str
    probable_cause: str
    confidence: float
    recommended_actions: tuple[str, ...]
    pm_counters: tuple[str, ...] = ()


# Telecom-grade gNB/DU/CU syslog signatures (3GPP-aligned causes)
SYSLOG_SIGNATURES: tuple[SyslogSignature, ...] = (
    SyslogSignature(
        "syslog_ngap_ho_failure",
        re.compile(r"NGAP.*HandoverPreparationFailure|HO.*prep.*fail|NGAP.*HO.*failure", re.I),
        "handover",
        "NGAP HandoverPreparationFailure — AMF or target gNB rejected HO prep",
        0.84,
        ("Check NGAP cause code", "Verify N2 connectivity", "Audit neighbor relation and TAC"),
        ("ho_prep_fail_rate", "ho_n2_fail_rate"),
    ),
    SyslogSignature(
        "syslog_xnap_failure",
        re.compile(r"XnAP.*failure|Xn.*setup.*fail|SCTP.*Xn", re.I),
        "handover",
        "XnAP interface failure — inter-gNB mobility path down",
        0.83,
        ("Check Xn SCTP/IPsec", "Verify Xn neighbor relation", "Review XnAP cause in trace"),
        ("ho_xn_fail_rate",),
    ),
    SyslogSignature(
        "syslog_rlf_out_of_sync",
        re.compile(r"RLF|radio link failure|out.?of.?sync|T310.*expir|N310.*max", re.I),
        "rlf",
        "Radio Link Failure — out-of-sync / timer expiry (T310/N310)",
        0.86,
        ("Correlate with RSRP at failure point", "Review coverage at cell edge", "Check interference"),
        ("rlf_rate", "out_of_sync_events"),
    ),
    SyslogSignature(
        "syslog_rach_preamble_collision",
        re.compile(r"RACH.*fail|PRACH.*preamble|MSG1.*fail|random access.*fail", re.I),
        "rach",
        "RACH/PRACH failure — preamble detection or MSG1 timeout",
        0.81,
        ("Audit prach-ConfigurationIndex", "Check PCI/PRACH plan", "Review UL interference"),
        ("rach_msg1_fail_rate", "rach_success_rate"),
    ),
    SyslogSignature(
        "syslog_rrc_reject",
        re.compile(r"RRC.*reject|RRCSetupReject|RRCReestablishmentReject", re.I),
        "rach",
        "RRC setup/re-establishment reject — accessibility failure",
        0.79,
        ("Check cell load and barring", "Verify SIB broadcast", "Review AMF reachability"),
        ("rrc_setup_fail_rate", "rach_success_rate"),
    ),
    SyslogSignature(
        "syslog_pdcp_discard",
        re.compile(r"PDCP.*discard|PDCP.*timeout|data.*radio.*link.*fail", re.I),
        "throughput",
        "PDCP discard/timeout — throughput degradation on radio path",
        0.77,
        ("Check BLER and MCS", "Review scheduler/congestion", "Validate QoS bearer mapping"),
        ("bler", "throughput_mbps", "prb_utilization"),
    ),
    SyslogSignature(
        "syslog_vonr_qfi_setup_fail",
        re.compile(r"5QI.?1|VoNR|IMS.*registration.*fail|QFI.*setup.*fail|voice.*bearer", re.I),
        "vonr",
        "VoNR/5QI-1 QoS flow setup failure — voice bearer not established",
        0.82,
        ("Verify 5QI-1/65 profile on SMF", "Check IMS P-CSCF reachability", "Audit NR coverage for VoNR"),
        ("vonr_setup_success_rate", "ims_registration_rate"),
    ),
    SyslogSignature(
        "syslog_amf_release",
        re.compile(r"AMF.*release|5GMM.*cause|NGAP.*UEContextRelease", re.I),
        "core",
        "AMF-initiated UE context release — core/session tear-down",
        0.78,
        ("Inspect 5GMM cause", "Verify subscription profile", "Check AMF load"),
        ("amf_release_rate", "drop_core_pct"),
    ),
    SyslogSignature(
        "syslog_du_crash",
        re.compile(r"DU.*crash|CU.*crash|process.*exit|F1.*link.*down|cell.*outage", re.I),
        "cell_outage",
        "Cell outage — DU/CU process or F1 link failure",
        0.88,
        ("Check FM alarms", "Restore F1/fronthaul", "Restart DU/CU pod and validate sync"),
        ("cell_availability",),
    ),
    SyslogSignature(
        "syslog_transport_loss",
        re.compile(r"packet.*loss|GTP.*drop|backhaul.*congest|N3.*loss", re.I),
        "transport",
        "Transport packet loss — backhaul/N3 congestion affecting KPIs",
        0.76,
        ("Check switch/router counters", "Verify QoS on N3", "Upgrade transport capacity"),
        ("transport_loss_rate", "backhaul_utilization"),
    ),
    SyslogSignature(
        "syslog_pci_conflict",
        re.compile(r"PCI.*conflict|PCI.*collision|confusion.*PCI", re.I),
        "anr",
        "PCI conflict/confusion detected — ANR or planning issue",
        0.80,
        ("Run PCI audit", "Enable ANR PCI correction", "Update neighbor PCI map"),
        ("pci_conflict_count",),
    ),
)


def parse_syslog_dataframe(df) -> list[dict[str, Any]]:
    """Parse structured gNB syslog CSV rows into signature findings."""
    if df is None or df.empty:
        return []
    lines = []
    for _, row in df.iterrows():
        module = str(row.get("module", ""))
        code = str(row.get("event_code", ""))
        msg = str(row.get("message", ""))
        lines.append(f"{module} {code} {msg}")
    text = "\n".join(lines)
    findings = parse_syslog_text(text, max_matches=15)

    # Map CSV event_code to signatures when regex miss
    code_map = {
        "HO_PREP_FAIL": "syslog_ngap_ho_failure",
        "XN_TIMEOUT": "syslog_xnap_failure",
        "T310_EXPIRY": "syslog_rlf_out_of_sync",
        "MSG1_FAIL": "syslog_rach_preamble_collision",
        "BEAM_OVERLOAD": "syslog_pdcp_discard",
        "SIP_TIMEOUT": "syslog_vonr_qfi_setup_fail",
    }
    seen = {f["rule_id"] for f in findings}
    if "event_code" in df.columns:
        for code, sig_id in code_map.items():
            if sig_id in seen:
                continue
            if (df["event_code"] == code).any():
                sig = next((s for s in SYSLOG_SIGNATURES if s.sig_id == sig_id), None)
                if sig:
                    seen.add(sig_id)
                    findings.append({
                        "rule_id": sig.sig_id,
                        "category": "gnb_syslog",
                        "domain": sig.domain,
                        "probable_cause": f"{sig.probable_cause} (CSV event_code={code})",
                        "confidence": sig.confidence,
                        "evidence": {"signature": sig_id, "event_code": code, "count": int((df["event_code"] == code).sum())},
                        "recommended_actions": list(sig.recommended_actions),
                        "pm_counters": list(sig.pm_counters),
                    })
    findings.sort(key=lambda x: x["confidence"], reverse=True)
    return findings


def parse_syslog_text(text: str, max_matches: int = 10) -> list[dict[str, Any]]:
    """Match syslog signatures against raw log text."""
    if not text or not text.strip():
        return []
    findings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sig in SYSLOG_SIGNATURES:
        if sig.sig_id in seen:
            continue
        if sig.pattern.search(text):
            seen.add(sig.sig_id)
            findings.append({
                "rule_id": sig.sig_id,
                "category": "gnb_syslog",
                "domain": sig.domain,
                "probable_cause": sig.probable_cause,
                "confidence": sig.confidence,
                "evidence": {"signature": sig.sig_id, "log_excerpt": text[:200]},
                "recommended_actions": list(sig.recommended_actions),
                "pm_counters": list(sig.pm_counters),
            })
            if len(findings) >= max_matches:
                break
    findings.sort(key=lambda x: x["confidence"], reverse=True)
    return findings
