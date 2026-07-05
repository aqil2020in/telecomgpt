"""Shared helpers for the multipage telecom dashboard."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_DEFAULT_DATASETS = Path("/workspace/datasets")
if _DEFAULT_DATASETS.exists():
    os.environ.setdefault("TNIC_DATASETS_DIR", str(_DEFAULT_DATASETS))
else:
    os.environ.setdefault("TNIC_DATASETS_DIR", str(ROOT / "data" / "datasets"))

from tnic.agents.ue_agent import UEProtocolAgent  # noqa: E402
from tnic.agents.specialists import (  # noqa: E402
    AGENT_REGISTRY,
    AlarmAgent,
    ANRAgent,
    BeamformingAgent,
    CallDropAgent,
    ConfigAuditAgent,
    GNBSyslogAgent,
    HOAgent,
    RACHAgent,
    RLFAgent,
    ThroughputAgent,
    VoNRAgent,
)
from tnic.datasets.kpi_service import build_kpi_input, compute_cell_kpis, compute_cluster_kpis, list_cell_ids
from tnic.datasets.loaders import (
    clear_loader_cache,
    load_alarm_events,
    load_anr_events,
    load_call_drop_events,
    load_cell_configuration,
    load_gnb_syslog,
    load_handover_events,
    load_neighbor_relations,
    load_pm_counters,
    load_rach_events,
    load_rlf_events,
    load_throughput_metrics,
    load_ue_protocol_trace,
    load_vonr_sessions,
)
from tnic.models.schemas import AnalyzeRequest
from tnic.orchestrator.rca_orchestrator import MasterRCAOrchestrator
from tnic.services.health_scoring import compute_health_score

DEMO_CELLS = [f"XYZ{i}" for i in range(401, 411)]
DOMAIN_QUERIES = {
    "handover": "handover failure cell {cell}",
    "rlf": "RLF radio link failure cell {cell}",
    "call_drop": "call drop cell {cell}",
    "rach": "RACH failure cell {cell}",
    "throughput": "low throughput cell {cell}",
    "beamforming": "beam failure cell {cell}",
    "vonr": "VoNR drop voice failure cell {cell}",
    "anr": "ANR PCI conflict missing neighbor cell {cell}",
    "config_audit": "configuration drift CM audit cell {cell}",
    "gnb_syslog": "gNB syslog NGAP XnAP failure cell {cell}",
    "alarm": "FM alarm correlation transport cell {cell}",
    "ue_protocol": "UE protocol trace RACH RRC NAS failure cell {cell}",
}

# All specialist agents (legacy + upgraded RCA agents)
ALL_AGENTS: list[tuple[str, str]] = [
    ("handover", "Handover"),
    ("rlf", "RLF"),
    ("call_drop", "Call Drop"),
    ("rach", "RACH"),
    ("throughput", "Throughput"),
    ("beamforming", "Beamforming"),
    ("vonr", "VoNR"),
    ("anr", "ANR"),
    ("config_audit", "Config Audit"),
    ("gnb_syslog", "gNB Syslog"),
    ("alarm", "Alarm Correlation"),
    ("ue_protocol", "UE Protocol"),
]

_AGENT_CLASSES = {
    "handover": HOAgent,
    "rlf": RLFAgent,
    "call_drop": CallDropAgent,
    "rach": RACHAgent,
    "throughput": ThroughputAgent,
    "beamforming": BeamformingAgent,
    "vonr": VoNRAgent,
    "anr": ANRAgent,
    "config_audit": ConfigAuditAgent,
    "gnb_syslog": GNBSyslogAgent,
    "alarm": AlarmAgent,
    "ue_protocol": UEProtocolAgent,
}


def dataset_cells() -> list[str]:
    cells = list_cell_ids()
    ordered = [c for c in DEMO_CELLS if c in cells]
    extras = sorted(c for c in cells if c not in ordered)
    return ordered + extras or DEMO_CELLS


def default_cell() -> str:
    cells = dataset_cells()
    return "XYZ401" if "XYZ401" in cells else cells[0]


@lru_cache(maxsize=32)
def cell_bundle(cell_id: str):
    clear_loader_cache()
    return compute_cell_kpis(cell_id)


def cell_kpis(cell_id: str) -> dict[str, Any]:
    return dict(cell_bundle(cell_id).kpis)


def cell_health(cell_id: str) -> dict[str, Any]:
    bundle = cell_bundle(cell_id)
    health = compute_health_score(bundle.kpis)
    health["overall_score"] = bundle.health_score or health["overall_score"]
    return health


def executive_summary_df() -> pd.DataFrame:
    rows = []
    for cell in dataset_cells():
        bundle = cell_bundle(cell)
        kpis = bundle.kpis
        health = cell_health(cell)
        rows.append({
            "cell_id": cell,
            "health_score": health["overall_score"],
            "grade": health["grade"],
            "ho_success_rate": kpis.get("ho_success_rate"),
            "rlf_rate": kpis.get("rlf_rate"),
            "call_drop_rate": kpis.get("call_drop_rate"),
            "rach_success_rate": kpis.get("rach_success_rate"),
            "throughput_mbps": kpis.get("throughput_mbps"),
            "ss_rsrp": kpis.get("ss_rsrp"),
            "ss_sinr": kpis.get("ss_sinr"),
        })
    return pd.DataFrame(rows)


def handover_df(cell_id: str | None = None) -> pd.DataFrame:
    df = load_handover_events()
    if cell_id:
        df = df[df["cell_id"] == cell_id]
    return df


def rlf_df(cell_id: str | None = None) -> pd.DataFrame:
    df = load_rlf_events()
    if cell_id:
        df = df[df["cell_id"] == cell_id]
    return df


def call_drop_df(cell_id: str | None = None) -> pd.DataFrame:
    df = load_call_drop_events()
    if cell_id:
        df = df[df["cell_id"] == cell_id]
    return df


def rach_df(cell_id: str | None = None) -> pd.DataFrame:
    df = load_rach_events()
    if cell_id:
        df = df[df["cell_id"] == cell_id]
    return df


def throughput_df(cell_id: str | None = None) -> pd.DataFrame:
    df = load_throughput_metrics()
    if cell_id:
        df = df[df["cell_id"] == cell_id]
    return df


def pm_df(cell_id: str | None = None) -> pd.DataFrame:
    df = load_pm_counters()
    if cell_id:
        df = df[df["cell_id"] == cell_id]
    return df


def synthesize_beam_metrics(cell_id: str, num_beams: int = 8) -> pd.DataFrame:
    """Lightweight SSB beam profile for dashboard visualization."""
    kpis = cell_kpis(cell_id)
    base_rsrp = float(kpis.get("ss_rsrp") or -100)
    base_sinr = float(kpis.get("ss_sinr") or 8)
    base_prb = float(kpis.get("prb_utilization") or 55)
    try:
        cell_num = int("".join(c for c in cell_id if c.isdigit()) or "401")
    except ValueError:
        cell_num = 401
    tier = "bad" if cell_num <= 404 else "medium" if cell_num <= 408 else "good"

    rows: list[dict[str, Any]] = []
    for beam_idx in range(num_beams):
        edge = beam_idx in (0, num_beams - 1)
        center = abs(beam_idx - (num_beams - 1) / 2) < 1.5
        util = base_prb * (1.35 if center else 0.85 if edge else 1.0)
        if tier == "bad":
            util *= 1.12 if center else 0.92
        util = min(98.0, max(8.0, util + beam_idx * 2.5))
        rows.append({
            "beam_index": beam_idx,
            "beam_utilization": round(util, 1),
            "beam_switches": int(6 + beam_idx * 1.5 + (12 if tier == "bad" else 4)),
            "rsrp": round(base_rsrp + (beam_idx - 3.5) * 2.5 - (8 if edge and tier == "bad" else 0), 1),
            "sinr": round(base_sinr - abs(beam_idx - 3.5) * 1.0 - (3 if edge else 0), 1),
        })
    return pd.DataFrame(rows)


def pm_df(cell_id: str | None = None) -> pd.DataFrame:
    df = load_pm_counters()
    if cell_id:
        df = df[df["cell_id"] == cell_id]
    return df


def gnb_syslog_df(cell_id: str | None = None) -> pd.DataFrame:
    df = load_gnb_syslog()
    if cell_id:
        df = df[df["cell_id"] == cell_id]
    return df


def alarm_df(cell_id: str | None = None) -> pd.DataFrame:
    df = load_alarm_events()
    if cell_id:
        df = df[df["cell_id"] == cell_id]
    return df


def anr_events_df(cell_id: str | None = None) -> pd.DataFrame:
    df = load_anr_events()
    if cell_id:
        df = df[df["cell_id"] == cell_id]
    return df


def vonr_sessions_df(cell_id: str | None = None) -> pd.DataFrame:
    df = load_vonr_sessions()
    if cell_id:
        df = df[df["cell_id"] == cell_id]
    return df


def cell_config_df(cell_id: str | None = None) -> pd.DataFrame:
    df = load_cell_configuration()
    if cell_id:
        df = df[df["cell_id"] == cell_id]
    return df


def neighbor_relations_df(cell_id: str | None = None) -> pd.DataFrame:
    df = load_neighbor_relations()
    if cell_id:
        df = df[df["source_cell"] == cell_id]
    return df


def ue_trace_df(cell_id: str | None = None) -> pd.DataFrame:
    df = load_ue_protocol_trace()
    if cell_id:
        df = df[df["cell_id"] == cell_id]
    return df


def run_all_agents(cell_id: str) -> list[dict[str, Any]]:
    """Run every registered specialist agent for dashboard comparison."""
    return [run_agent(name, cell_id) for name, _ in ALL_AGENTS]


def run_agent(agent_name: str, cell_id: str) -> dict[str, Any]:
    kpis = {**cell_kpis(cell_id), "cell_id": cell_id}
    query = DOMAIN_QUERIES.get(agent_name, f"{agent_name} cell {cell_id}").format(cell=cell_id)
    # gNB Syslog agent needs log text in KPIs/query
    if agent_name == "gnb_syslog":
        kpis["syslog_text"] = kpis.get("syslog_text") or query
    cls = _AGENT_CLASSES.get(agent_name)
    if not cls:
        reg = AGENT_REGISTRY.get(agent_name)
        if reg:
            result = reg.analyze(kpis, query=query)
            return {
                "agent": result.agent,
                "summary": result.summary,
                "findings": [f.model_dump() for f in result.findings[:8]],
            }
        return {"agent": agent_name, "findings": [], "summary": "Unknown agent"}
    result = cls().analyze(kpis, query=query)
    return {
        "agent": result.agent,
        "summary": result.summary,
        "findings": [f.model_dump() for f in result.findings[:8]],
    }


def run_rca(cell_id: str, query: str, generate_report: bool = False) -> Any:
    kpi_input = build_kpi_input(cell_id=cell_id, query=query)
    req = AnalyzeRequest(
        query=query,
        kpis=kpi_input,
        include_rag=False,
        generate_report=generate_report,
    )
    return MasterRCAOrchestrator().run(req)


def worst_cells(n: int = 5) -> list[str]:
    try:
        cluster = compute_cluster_kpis()
        return cluster.worst_cells[:n]
    except Exception:
        df = executive_summary_df()
        if df.empty:
            return dataset_cells()[:n]
        return df.nsmallest(n, "health_score")["cell_id"].tolist()
