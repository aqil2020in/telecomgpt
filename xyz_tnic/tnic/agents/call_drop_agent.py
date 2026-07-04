"""5G Call Drop Agent — classifies drops from call_drop_events.csv."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from tnic.datasets.loaders import load_call_drop_events

DROP_CODES = frozenset({"RADIO", "MOBILITY", "IMS", "CORE", "TRANSPORT"})

DROP_LABELS: dict[str, str] = {
    "RADIO": "Radio Drop",
    "MOBILITY": "Mobility Drop",
    "IMS": "IMS Drop",
    "CORE": "Core Drop",
    "TRANSPORT": "Transport Drop",
}

# CSV drop_type column -> internal code
CSV_DROP_MAP: dict[str, str] = {
    "RADIO": "RADIO",
    "MOBILITY": "MOBILITY",
    "IMS": "IMS",
    "CORE": "CORE",
    "TRANSPORT": "TRANSPORT",
}

ROOT_CAUSES: dict[str, str] = {
    "RADIO": (
        "Radio layer call drop — RLF, coverage hole, or RF degradation triggered "
        "RRC release before reestablishment succeeded."
    ),
    "MOBILITY": (
        "Mobility-related call drop — handover failure, too-late HO, or ping-pong "
        "between neighbors caused session release during mobility."
    ),
    "IMS": (
        "IMS/VoNR call drop — voice bearer (5QI-1) or IMS registration path failed; "
        "often SIP timeout or codec mismatch on VoNR leg."
    ),
    "CORE": (
        "Core network call drop — AMF/SMF-initiated PDU session release with healthy "
        "RAN RF; investigate 5GMM cause and subscription state."
    ),
    "TRANSPORT": (
        "Transport/backhaul call drop — N3/N6 congestion or packet loss on backhaul "
        "caused user-plane starvation and session abort."
    ),
}

BASE_CONFIDENCE: dict[str, float] = {
    "RADIO": 0.83,
    "MOBILITY": 0.78,
    "IMS": 0.76,
    "CORE": 0.74,
    "TRANSPORT": 0.72,
}

QUERY_HINTS: dict[str, str] = {
    "radio drop": "RADIO",
    "radio layer": "RADIO",
    "rlf drop": "RADIO",
    "mobility drop": "MOBILITY",
    "mobility": "MOBILITY",
    "handover drop": "MOBILITY",
    "ho drop": "MOBILITY",
    "ims drop": "IMS",
    "vonr": "IMS",
    "vo nr": "IMS",
    "core drop": "CORE",
    "core release": "CORE",
    "amf": "CORE",
    "smf release": "CORE",
    "transport drop": "TRANSPORT",
    "backhaul": "TRANSPORT",
    "n3 drop": "TRANSPORT",
}


@dataclass(frozen=True)
class CallDropDiagnosis:
    """Structured call drop diagnosis."""

    drop_class: str
    root_cause: str
    confidence: float
    cell_id: str | None = None
    evidence: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_cause": self.root_cause,
            "confidence": round(self.confidence, 2),
        }


class CallDropAgent:
    """Telecom-grade call drop classifier over call_drop_events.csv."""

    name = "call_drop_agent"

    def analyze(
        self,
        cell_id: str | None = None,
        query: str = "",
        events: pd.DataFrame | None = None,
        csv_path: str | Path | None = None,
    ) -> CallDropDiagnosis:
        df = self._load_events(events, csv_path)
        if cell_id and not df.empty and "cell_id" in df.columns:
            df = df[df["cell_id"] == cell_id]
        if df.empty:
            return CallDropDiagnosis(
                drop_class="No Data",
                root_cause="No call drop events found for the requested scope.",
                confidence=0.0,
                cell_id=cell_id,
            )

        labeled = _label_events(df)
        drops = labeled[labeled["drop_code"].isin(DROP_CODES)]
        if drops.empty:
            return CallDropDiagnosis(
                drop_class="No Drop",
                root_cause="No labeled call drop events — all sessions normal in sample window.",
                confidence=0.5,
                cell_id=cell_id or str(df["cell_id"].mode().iloc[0]),
            )

        counts = drops["drop_code"].value_counts()
        hinted = _drop_from_query(query)
        code = hinted if hinted else str(counts.index[0])
        subset = drops[drops["drop_code"] == code]
        if subset.empty and hinted:
            subset = drops.head(3)
            confidence = round(min(BASE_CONFIDENCE.get(code, 0.65), 0.75), 2)
        else:
            confidence = _score_confidence(code, counts, len(drops), len(labeled))

        root = _format_root_cause(code, subset if not subset.empty else drops.head(3), counts)
        evidence = _build_evidence(drops, subset if not subset.empty else drops, code)

        return CallDropDiagnosis(
            drop_class=DROP_LABELS.get(code, code),
            root_cause=root,
            confidence=confidence,
            cell_id=cell_id or str(drops["cell_id"].mode().iloc[0]),
            evidence=evidence,
        )

    def analyze_kpis(self, kpis: dict[str, Any], query: str = "") -> CallDropDiagnosis:
        cell_id = kpis.get("cell_id")
        if cell_id:
            return self.analyze(cell_id=str(cell_id), query=query)
        return self.analyze(query=query)

    def _load_events(
        self,
        events: pd.DataFrame | None,
        csv_path: str | Path | None,
    ) -> pd.DataFrame:
        if events is not None:
            df = events.copy()
        elif csv_path is not None:
            df = pd.read_csv(csv_path)
        else:
            df = load_call_drop_events()
        df.columns = [c.strip().lower() for c in df.columns]
        return df


def _normalize_drop_type(raw: str | None) -> str | None:
    if raw is None or pd.isna(raw):
        return None
    key = str(raw).strip().upper()
    if key in ("NONE", "", "NAN"):
        return None
    return CSV_DROP_MAP.get(key)


def _label_events(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["drop_code"] = out["drop_type"].apply(_normalize_drop_type)
    return out


def _drop_from_query(query: str) -> str | None:
    ql = query.lower()
    for hint, code in sorted(QUERY_HINTS.items(), key=lambda x: len(x[0]), reverse=True):
        if hint in ql:
            return code
    return None


def _build_evidence(all_drops: pd.DataFrame, subset: pd.DataFrame, code: str) -> dict[str, Any]:
    total = len(all_drops)
    type_n = len(subset)
    return {
        "drop_code": code,
        "drop_class": DROP_LABELS.get(code, code),
        "drop_count": int(type_n),
        "total_drops": int(total),
        "drop_share_pct": round(100.0 * type_n / total, 2) if total else 0.0,
        "drop_distribution": {
            DROP_LABELS.get(k, k): int(v)
            for k, v in all_drops["drop_code"].value_counts().items()
        },
    }


def _score_confidence(code: str, counts: pd.Series, drop_total: int, event_total: int) -> float:
    base = BASE_CONFIDENCE.get(code, 0.70)
    type_count = int(counts.get(code, 0))
    dominance = type_count / drop_total if drop_total else 0.0
    rate = drop_total / event_total if event_total else 0.0
    score = base * 0.50 + dominance * 0.35 + min(rate, 1.0) * 0.15
    if drop_total >= 50:
        score += 0.03
    elif drop_total < 15:
        score -= 0.05
    return round(min(max(score, 0.40), 0.95), 2)


def _format_root_cause(code: str, subset: pd.DataFrame, counts: pd.Series) -> str:
    base = ROOT_CAUSES.get(code, "Call drop detected — review drop counters and UE trace.")
    type_count = int(counts.get(code, len(subset)))
    drop_total = int(counts.sum())
    pct = round(100.0 * type_count / drop_total, 1) if drop_total else 0.0
    label = DROP_LABELS.get(code, code)
    return (
        f"{label}: {base} "
        f"({type_count}/{drop_total} drops, {pct}% of cell drop mix)."
    )


def diagnose_call_drop(
    cell_id: str | None = None,
    query: str = "",
    csv_path: str | Path | None = None,
) -> dict[str, Any]:
    """Convenience API — returns {root_cause, confidence}."""
    return CallDropAgent().analyze(cell_id=cell_id, query=query, csv_path=csv_path).to_dict()
