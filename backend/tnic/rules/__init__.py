"""Rule engine registry."""

from tnic.rules.beamforming_rules import BEAMFORMING_RULE_ENGINE
from tnic.rules.call_drop_rules import CALL_DROP_RULE_ENGINE
from tnic.rules.ho_rules import HO_RULE_ENGINE
from tnic.rules.latency_rules import LATENCY_RULE_ENGINE
from tnic.rules.rach_rules import RACH_RULE_ENGINE
from tnic.rules.rlf_rules import RLF_RULE_ENGINE
from tnic.rules.throughput_rules import THROUGHPUT_RULE_ENGINE

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
}

ISSUE_KEYWORDS = {
    "handover": ("handover", "ho fail", "ho failure", "mobility", "ping pong", "xn"),
    "rlf": ("rlf", "radio link failure", "out of sync", "t310", "n310"),
    "call_drop": ("call drop", "dropped call", "qdrop", "context release"),
    "throughput": ("throughput", "tput", "low mcs", "bler", "cqi"),
    "rach": ("rach", "prach", "msg3", "random access"),
    "beamforming": ("beam", "beamforming", "beam failure", "ssb"),
    "latency": ("latency", "rtt", "upf", "5qi delay", "pdu setup"),
    "transport": ("transport", "backhaul", "n3", "n6", "congestion"),
    "core": ("core", "amf", "smf", "upf", "5gmm", "pdu session"),
    "complaint": ("complaint", "customer", "subscriber", "ticket"),
}


def detect_issue_type(query: str, explicit: str | None = None) -> str:
    if explicit and explicit.lower() in RULE_ENGINES:
        return explicit.lower()
    ql = query.lower()
    scores: dict[str, int] = {}
    for issue, keywords in ISSUE_KEYWORDS.items():
        scores[issue] = sum(1 for kw in keywords if kw in ql)
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return "handover"
    if best in ("transport", "core", "complaint"):
        return best
    return best if best in RULE_ENGINES else "handover"
