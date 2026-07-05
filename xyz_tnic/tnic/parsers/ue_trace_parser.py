"""UE protocol trace parser — layer/procedure/message classification."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from tnic.datasets.registry import DatasetName, dataset_path


# Supported layer → procedure → message taxonomy (3GPP-aligned)
LAYER_PROCEDURES: dict[str, tuple[str, ...]] = {
    "PHY": ("CELL_SEARCH", "MIB", "BEAM", "SYNC"),
    "SIB": ("SIB1", "SIB2", "SI_ACQUISITION"),
    "RACH": ("ACCESS", "MSG1", "MSG2", "MSG3", "MSG4", "RETRANSMISSION"),
    "RRC": ("CONNECTION", "SECURITY", "RECONFIGURATION", "DRB", "RELEASE", "RESUME", "REESTABLISHMENT", "RLF", "PAGING"),
    "NAS": ("REGISTRATION", "AUTHENTICATION", "DEREGISTRATION", "SERVICE"),
    "MEASUREMENT": ("A1", "A2", "A3", "A5", "REPORT"),
    "MOBILITY": ("HANDOVER", "PING_PONG", "TOO_EARLY", "TOO_LATE"),
    "5GSM": ("PDU_SESSION", "QOS_FLOW", "SESSION_MODIFICATION", "SESSION_RELEASE"),
    "IMS": ("VONR", "SIP", "REGISTRATION"),
    "BEAM": ("BEAM_MGMT", "BEAM_SWITCH", "BEAM_FAILURE"),
    "PAGING": ("PAGING", "SERVICE_REQUEST"),
}

# Map trace row → failure scenario key
MESSAGE_SCENARIO_MAP: dict[str, str] = {
    "PBCH_DECODE_FAILURE": "MIB_DECODE_FAILURE",
    "MIB_DECODE_FAILURE": "MIB_DECODE_FAILURE",
    "SIB1_DECODE_FAILURE": "SIB_ACQUISITION_FAILURE",
    "SIB1_DECODE_FAIL": "SIB_ACQUISITION_FAILURE",
    "RACH_FAILURE": "RACH_FAILURE",
    "MSG1_TIMEOUT": "RACH_FAILURE",
    "MSG3_FAILURE": "RACH_FAILURE",
    "RRC_SETUP_FAILURE": "RRC_SETUP_FAILURE",
    "RRC_SETUP_REJECT": "RRC_SETUP_FAILURE",
    "AUTH_FAILURE": "AUTHENTICATION_FAILURE",
    "REGISTRATION_REJECT": "REGISTRATION_FAILURE",
    "PAGING_RESPONSE_TIMEOUT": "PAGING_FAILURE",
    "PAGING_FAILURE": "PAGING_FAILURE",
    "HO_FAILURE": "HO_FAILURE",
    "RETURN_TO_SOURCE_CELL": "PING_PONG_HO",
    "PING_PONG_HO": "PING_PONG_HO",
    "TOO_EARLY_HO": "TOO_EARLY_HO",
    "TOO_LATE_HO": "TOO_LATE_HO",
    "T310_EXPIRY": "T310_EXPIRY",
    "RLF": "RADIO_LINK_FAILURE",
    "OUT_OF_SYNC": "RADIO_LINK_FAILURE",
    "REESTABLISHMENT_FAILURE": "RE_ESTABLISHMENT_FAILURE",
    "PDU_SESSION_REJECT": "PDU_SESSION_FAILURE",
    "QOS_FLOW_SETUP_FAIL": "QOS_FLOW_FAILURE",
    "DRB_SETUP_FAILURE": "DRB_SETUP_FAILURE",
    "BEAM_INSTABILITY": "BEAM_INSTABILITY",
    "VONR_DROP": "VONR_DROP",
    "SIP_TIMEOUT": "IMS_FAILURE",
    "SIP_FAILURE": "IMS_FAILURE",
}

CAUSE_SCENARIO_MAP: dict[str, str] = {
    "NO_RAR_RESPONSE": "RACH_FAILURE",
    "LOW_SINR": "INTERFERENCE",
    "COVERAGE_HOLE": "COVERAGE_HOLE",
    "HO_PREP_FAILURE": "HO_FAILURE",
    "PING_PONG_HO": "PING_PONG_HO",
    "IMS_TIMEOUT": "IMS_FAILURE",
    "QFI_MAPPING_ERROR": "QOS_FLOW_FAILURE",
    "CELL_CONGESTION": "RRC_SETUP_FAILURE",
    "AUTH_TIMEOUT": "AUTHENTICATION_FAILURE",
    "TA_NOT_ALLOWED": "REGISTRATION_FAILURE",
    "T3417_EXPIRY": "PAGING_FAILURE",
    "RADIO_RESOURCE_UNAVAILABLE": "DRB_SETUP_FAILURE",
    "EXCESSIVE_SWITCHING": "BEAM_INSTABILITY",
}


@dataclass
class UETraceEvent:
    timestamp: str
    ue_id: str
    cell_id: str
    layer: str
    procedure: str
    message: str
    result: str
    cause: str = ""

    @property
    def is_failure(self) -> bool:
        return str(self.result).upper() in ("FAIL", "FAILURE", "DROP", "REJECT", "TIMEOUT")

    def scenario_key(self) -> str | None:
        msg = self.message.upper()
        if msg in MESSAGE_SCENARIO_MAP:
            return MESSAGE_SCENARIO_MAP[msg]
        if self.cause and self.cause.upper() in CAUSE_SCENARIO_MAP:
            return CAUSE_SCENARIO_MAP[self.cause.upper()]
        if self.is_failure:
            return f"{self.layer}_{self.procedure}_FAILURE".upper()
        return None


@dataclass
class UETraceSession:
    ue_id: str
    cell_id: str
    events: list[UETraceEvent] = field(default_factory=list)
    failures: list[UETraceEvent] = field(default_factory=list)

    def last_failure(self) -> UETraceEvent | None:
        return self.failures[-1] if self.failures else None

    def failure_stages(self) -> list[str]:
        return [f"{e.layer}/{e.procedure}/{e.message}" for e in self.failures]


@lru_cache(maxsize=1)
def load_ue_protocol_trace(path: str | None = None) -> pd.DataFrame:
    p = Path(path) if path else dataset_path(DatasetName.UE_PROTOCOL_TRACE)
    df = pd.read_csv(p)
    df.columns = [c.strip().lower() for c in df.columns]
    if "timestamp" in df.columns:
        df["timestamp"] = df["timestamp"].astype(str)
    return df


class UETraceParser:
    """Parse UE protocol trace CSV into structured sessions and failure events."""

    def __init__(self, path: str | None = None):
        self._path = path

    def load(self) -> pd.DataFrame:
        return load_ue_protocol_trace(self._path)

    def parse_events(self, df: pd.DataFrame | None = None) -> list[UETraceEvent]:
        df = df if df is not None else self.load()
        events: list[UETraceEvent] = []
        for _, row in df.iterrows():
            events.append(UETraceEvent(
                timestamp=str(row.get("timestamp", "")),
                ue_id=str(row.get("ue_id", "")),
                cell_id=str(row.get("cell_id", "")),
                layer=str(row.get("layer", "")).upper(),
                procedure=str(row.get("procedure", "")).upper(),
                message=str(row.get("message", "")).upper(),
                result=str(row.get("result", "")).upper(),
                cause=str(row.get("cause", "") or "").upper(),
            ))
        return events

    def sessions_by_ue(self, df: pd.DataFrame | None = None) -> dict[str, UETraceSession]:
        sessions: dict[str, UETraceSession] = {}
        for ev in self.parse_events(df):
            key = ev.ue_id
            if key not in sessions:
                sessions[key] = UETraceSession(ue_id=ev.ue_id, cell_id=ev.cell_id)
            sessions[key].events.append(ev)
            if ev.is_failure:
                sessions[key].failures.append(ev)
        return sessions

    def failures_for_cell(self, cell_id: str, df: pd.DataFrame | None = None) -> list[UETraceEvent]:
        cid = cell_id.upper()
        return [e for e in self.parse_events(df) if e.cell_id.upper() == cid and e.is_failure]

    def failures_for_ue(self, ue_id: str, df: pd.DataFrame | None = None) -> list[UETraceEvent]:
        uid = ue_id.upper()
        return [e for e in self.parse_events(df) if e.ue_id.upper() == uid and e.is_failure]

    def cell_summary(self, cell_id: str, df: pd.DataFrame | None = None) -> dict[str, Any]:
        fails = self.failures_for_cell(cell_id, df)
        by_scenario: dict[str, int] = {}
        by_layer: dict[str, int] = {}
        for f in fails:
            sk = f.scenario_key() or "UNKNOWN"
            by_scenario[sk] = by_scenario.get(sk, 0) + 1
            by_layer[f.layer] = by_layer.get(f.layer, 0) + 1
        return {
            "cell_id": cell_id.upper(),
            "failure_count": len(fails),
            "ue_count": len({f.ue_id for f in fails}),
            "by_scenario": by_scenario,
            "by_layer": by_layer,
            "failures": [
                {
                    "ue_id": f.ue_id,
                    "layer": f.layer,
                    "procedure": f.procedure,
                    "message": f.message,
                    "cause": f.cause,
                    "scenario": f.scenario_key(),
                }
                for f in fails
            ],
        }
