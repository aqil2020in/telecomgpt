"""Rule engine registry."""

from tnic.rules.alarm_rules import ALARM_RULE_ENGINE
from tnic.rules.anr_rules import ANR_RULE_ENGINE
from tnic.rules.beamforming_rules import BEAMFORMING_RULE_ENGINE
from tnic.rules.call_drop_rules import CALL_DROP_RULE_ENGINE
from tnic.rules.config_audit_rules import CONFIG_AUDIT_RULE_ENGINE
from tnic.rules.core_rules import CORE_RULE_ENGINE
from tnic.rules.coverage_rules import COVERAGE_RULE_ENGINE
from tnic.rules.gnb_syslog_rules import GNB_SYSLOG_RULE_ENGINE
from tnic.rules.ho_rules import HO_RULE_ENGINE
from tnic.rules.latency_rules import LATENCY_RULE_ENGINE
from tnic.rules.pm_validation_rules import PM_VALIDATION_RULE_ENGINE
from tnic.rules.rach_rules import RACH_RULE_ENGINE
from tnic.rules.rlf_rules import RLF_RULE_ENGINE
from tnic.rules.throughput_rules import THROUGHPUT_RULE_ENGINE
from tnic.rules.transport_rules import TRANSPORT_RULE_ENGINE
from tnic.rules.vonr_rules import VONR_RULE_ENGINE

RULE_ENGINES = {
    "handover": HO_RULE_ENGINE,
    "ho": HO_RULE_ENGINE,
    "rlf": RLF_RULE_ENGINE,
    "call_drop": CALL_DROP_RULE_ENGINE,
    "throughput": THROUGHPUT_RULE_ENGINE,
    "rach": RACH_RULE_ENGINE,
    "beamforming": BEAMFORMING_RULE_ENGINE,
    "beam": BEAMFORMING_RULE_ENGINE,
    "latency": LATENCY_RULE_ENGINE,
    "vonr": VONR_RULE_ENGINE,
    "anr": ANR_RULE_ENGINE,
    "config_audit": CONFIG_AUDIT_RULE_ENGINE,
    "gnb_syslog": GNB_SYSLOG_RULE_ENGINE,
    "coverage": COVERAGE_RULE_ENGINE,
    "transport": TRANSPORT_RULE_ENGINE,
    "core": CORE_RULE_ENGINE,
    "pm": PM_VALIDATION_RULE_ENGINE,
    "pm_validation": PM_VALIDATION_RULE_ENGINE,
    "alarm": ALARM_RULE_ENGINE,
}

ISSUE_KEYWORDS = {
    "handover": ("handover", "ho fail", "ho failure", "mobility", "ping pong", "xn", "too early", "too late"),
    "rlf": ("rlf", "radio link failure", "out of sync", "t310", "n310"),
    "call_drop": ("call drop", "dropped call", "qdrop", "context release"),
    "throughput": ("throughput", "tput", "low mcs", "bler", "cqi", "scheduler", "prb"),
    "rach": ("rach", "prach", "msg3", "random access", "rrc setup", "rrc fail"),
    "beamforming": ("beam", "beamforming", "beam failure", "ssb"),
    "latency": ("latency", "rtt", "upf", "5qi delay", "pdu setup"),
    "transport": ("transport", "backhaul", "n3", "n6", "congestion", "fronthaul"),
    "core": ("core", "amf", "smf", "upf", "5gmm", "pdu session", "ngap", "n2"),
    "complaint": ("complaint", "customer", "subscriber", "ticket"),
    "rf_coverage": (
        "coverage", "rsrp", "sinr", "coverage hole", "weak coverage",
        "interference", "beam gap", "geospatial", "drive test", "hotspot",
        "overshoot", "pilot pollution",
    ),
    "vonr": ("vonr", "volte", "voice", "5qi-1", "5qi 1", "ims", "mute call", "rtp", "vonr drop"),
    "anr": ("anr", "neighbor relation", "ncr", "pci conflict", "pci collision", "missing neighbor"),
    "config_audit": ("config audit", "parameter drift", "cm audit", "golden config", "a3 offset", "prach config", "config drift"),
    "gnb_syslog": ("syslog", "gnb log", "du crash", "cu crash", "ngap", "xnap", "cell outage", "log correlation"),
    "pm": ("pm validation", "counter integrity", "kpi mismatch", "counter definition"),
    "alarm": ("alarm", "fm alarm", "critical alarm", "alarm correlation"),
    "ue_protocol": (
        "ue trace", "ue protocol", "protocol trace", "mib decode", "sib1",
        "msg1", "msg2", "msg3", "msg4", "rrc setup", "security mode",
        "registration reject", "authentication", "paging failure", "t310",
        "re-establishment", "pdu session", "qos flow", "vonr drop", "sip timeout",
    ),
}

_EXTRA_ISSUE_TYPES = frozenset({
    "rf_coverage", "coverage", "transport", "core", "complaint",
    "vonr", "anr", "config_audit", "gnb_syslog", "pm", "alarm",
    "ue_protocol", "ue_trace",
})


def detect_issue_type(query: str, explicit: str | None = None) -> str:
    if explicit:
        exp = explicit.lower().replace("-", "_")
        if exp in RULE_ENGINES:
            return exp
        if exp in _EXTRA_ISSUE_TYPES:
            if exp == "coverage":
                return "rf_coverage"
            return exp
    ql = query.lower()
    scores: dict[str, int] = {}
    for issue, keywords in ISSUE_KEYWORDS.items():
        scores[issue] = sum(1 for kw in keywords if kw in ql)
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return "handover"
    if best in _EXTRA_ISSUE_TYPES:
        return "rf_coverage" if best == "rf_coverage" else best
    return best if best in RULE_ENGINES else "handover"
