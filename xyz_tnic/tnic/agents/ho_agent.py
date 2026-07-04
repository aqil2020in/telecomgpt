"""5G Handover Failure Agent — analyzes handover_events.csv for mobility RCA."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from tnic.datasets.loaders import load_handover_events

# CSV failure_type values in handover_events.csv
FAILURE_CODES = frozenset({
    "PREP_FAILURE",
    "EXEC_FAILURE",
    "XN_FAILURE",
    "N2_FAILURE",
    "TOO_EARLY_HO",
    "TOO_LATE_HO",
    "PING_PONG",
    "WRONG_CELL",
})

# Human-readable labels returned in diagnosis output
FAILURE_LABELS: dict[str, str] = {
    "PREP_FAILURE": "Prep Failure",
    "EXEC_FAILURE": "Execution Failure",
    "XN_FAILURE": "Xn Failure",
    "N2_FAILURE": "N2 Failure",
    "TOO_EARLY_HO": "Too Early HO",
    "TOO_LATE_HO": "Too Late HO",
    "PING_PONG": "Ping Pong",
    "WRONG_CELL": "Wrong Cell",
}

ROOT_CAUSES: dict[str, str] = {
    "PREP_FAILURE": (
        "HO preparation failed — target gNB/cell not ready, missing neighbor relation, "
        "or Xn/NG preparation timeout before execution."
    ),
    "EXEC_FAILURE": (
        "HO execution failed — RRC reconfiguration or sync failure during mobility; "
        "often RF degradation or timer expiry on source/target."
    ),
    "XN_FAILURE": (
        "Xn interface failure — inter-gNB XnAP HO preparation or resource setup "
        "failed (transport, SCTP/IPsec, or neighbor Xn relation)."
    ),
    "N2_FAILURE": (
        "N2/NGAP failure — AMF or NG interface rejected or timed out during HO "
        "(NGAP HandoverPreparationFailure or resource allocation)."
    ),
    "TOO_EARLY_HO": (
        "Too-early handover — mobility threshold too aggressive; UE handed over "
        "while source cell RF is still adequate."
    ),
    "TOO_LATE_HO": (
        "Too-late handover — A3/time-to-trigger insufficient; UE reached cell edge "
        "before HO trigger, risking RLF or QoS collapse."
    ),
    "PING_PONG": (
        "Ping-pong handover — hysteresis/CIO mis-tuned between neighbor pair; "
        "UE oscillates between cells."
    ),
    "WRONG_CELL": (
        "Wrong cell selection — HO target suboptimal vs best neighbor; incomplete "
        "neighbor list, beam priority, or ranking error."
    ),
}

# Base confidence when failure type is dominant (before RF/context adjustment)
BASE_CONFIDENCE: dict[str, float] = {
    "PREP_FAILURE": 0.82,
    "EXEC_FAILURE": 0.78,
    "XN_FAILURE": 0.80,
    "N2_FAILURE": 0.77,
    "TOO_EARLY_HO": 0.71,
    "TOO_LATE_HO": 0.73,
    "PING_PONG": 0.76,
    "WRONG_CELL": 0.69,
}

QUERY_HINTS: dict[str, str] = {
    "prep": "PREP_FAILURE",
    "preparation": "PREP_FAILURE",
    "execution": "EXEC_FAILURE",
    "exec": "EXEC_FAILURE",
    "xn": "XN_FAILURE",
    "n2": "N2_FAILURE",
    "ngap": "N2_FAILURE",
    "too early": "TOO_EARLY_HO",
    "too late": "TOO_LATE_HO",
    "ping pong": "PING_PONG",
    "ping-pong": "PING_PONG",
    "wrong cell": "WRONG_CELL",
}


@dataclass(frozen=True)
class HOFailureDiagnosis:
    """Structured HO failure diagnosis."""

    failure_type: str
    root_cause: str
    confidence: float
    cell_id: str | None = None
    evidence: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_type": self.failure_type,
            "root_cause": self.root_cause,
            "confidence": round(self.confidence, 2),
        }


class HandoverFailureAgent:
    """Telecom-grade 5G handover failure analyzer over handover_events.csv."""

    name = "ho_agent"

    def analyze(
        self,
        cell_id: str | None = None,
        query: str = "",
        events: pd.DataFrame | None = None,
        csv_path: str | Path | None = None,
    ) -> HOFailureDiagnosis:
        """Analyze handover events and return primary failure diagnosis."""
        df = self._load_events(events, csv_path)
        if cell_id:
            df = df[df["cell_id"] == cell_id]
        if df.empty:
            return HOFailureDiagnosis(
                failure_type="No Data",
                root_cause="No handover events found for the requested scope.",
                confidence=0.0,
                cell_id=cell_id,
            )

        failures = df[df["failure_type"].isin(FAILURE_CODES)]
        if failures.empty:
            return HOFailureDiagnosis(
                failure_type="No Failure",
                root_cause="All handover events succeeded — no mobility failure signature detected.",
                confidence=0.55,
                cell_id=cell_id or str(df["cell_id"].mode().iloc[0]),
                evidence={"ho_success_rate_pct": round(100.0 * len(df[df["failure_type"] == "SUCCESS"]) / len(df), 2)},
            )

        counts = failures["failure_type"].value_counts()
        hinted = _failure_from_query(query)
        if hinted:
            code = hinted
        else:
            code = str(counts.index[0])
        subset = failures[failures["failure_type"] == code]
        if subset.empty and hinted:
            # Operator-directed query with no matching events — still diagnose from hint
            subset = failures.head(1)
        evidence = _build_evidence(df, failures, subset if not subset.empty else failures, code)
        confidence = _score_confidence(code, counts, subset if not subset.empty else failures, len(df))
        if hinted and subset.empty:
            confidence = round(min(BASE_CONFIDENCE.get(code, 0.65), 0.75), 2)
        root = _root_cause_with_rf(code, subset if not subset.empty else failures.head(3))

        return HOFailureDiagnosis(
            failure_type=FAILURE_LABELS.get(code, code),
            root_cause=root,
            confidence=confidence,
            cell_id=cell_id or str(failures["cell_id"].mode().iloc[0]),
            evidence=evidence,
        )

    def analyze_kpis(self, kpis: dict[str, Any], query: str = "") -> HOFailureDiagnosis:
        """Entry point when only aggregated KPIs are available (uses cell_id to load events)."""
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
            df = load_handover_events()
        df.columns = [c.strip().lower() for c in df.columns]
        return df


def _failure_from_query(query: str) -> str | None:
    ql = query.lower()
    for hint, code in sorted(QUERY_HINTS.items(), key=lambda x: len(x[0]), reverse=True):
        if hint in ql:
            return code
    return None


def _build_evidence(
    all_events: pd.DataFrame,
    failures: pd.DataFrame,
    subset: pd.DataFrame,
    code: str,
) -> dict[str, Any]:
    total = len(all_events)
    fail_n = len(failures)
    type_n = len(subset)
    ev: dict[str, Any] = {
        "failure_code": code,
        "failure_count": int(type_n),
        "total_failures": int(fail_n),
        "total_events": int(total),
        "failure_share_pct": round(100.0 * type_n / fail_n, 2) if fail_n else 0.0,
        "ho_fail_rate_pct": round(100.0 * fail_n / total, 2) if total else 0.0,
        "failure_distribution": failures["failure_type"].value_counts().to_dict(),
    }
    for col in ("rsrp", "rsrq", "sinr"):
        if col in subset.columns and not subset.empty:
            ev[f"mean_{col}"] = round(float(subset[col].mean()), 2)
    return ev


def _score_confidence(
    code: str,
    counts: pd.Series,
    subset: pd.DataFrame,
    total_events: int,
) -> float:
    base = BASE_CONFIDENCE.get(code, 0.70)
    fail_total = int(counts.sum())
    type_count = int(counts.get(code, 0))
    dominance = type_count / fail_total if fail_total else 0.0
    rate = type_count / total_events if total_events else 0.0

    score = base * 0.45 + dominance * 0.35 + min(rate * 5.0, 1.0) * 0.20
    score = _rf_boost(code, subset, score)
    return round(min(max(score, 0.35), 0.95), 2)


def _rf_boost(code: str, subset: pd.DataFrame, score: float) -> float:
    if subset.empty or "rsrp" not in subset.columns:
        return score
    rsrp = float(subset["rsrp"].mean())
    sinr = float(subset["sinr"].mean()) if "sinr" in subset.columns else 0.0

    if code == "TOO_LATE_HO" and rsrp <= -110:
        score += 0.06
    elif code == "TOO_EARLY_HO" and rsrp > -95 and sinr > 10:
        score += 0.06
    elif code == "WRONG_CELL" and rsrp < -115:
        score += 0.05
    elif code in ("PREP_FAILURE", "XN_FAILURE", "N2_FAILURE") and rsrp <= -108:
        score += 0.03
    elif code == "PING_PONG" and -105 <= rsrp <= -95:
        score += 0.04
    return score


def _root_cause_with_rf(code: str, subset: pd.DataFrame) -> str:
    base = ROOT_CAUSES.get(code, "Handover failure detected — review mobility and neighbor configuration.")
    if subset.empty:
        return base
    parts = [base]
    if "rsrp" in subset.columns:
        rsrp = float(subset["rsrp"].mean())
        parts.append(f"Mean RSRP at failure: {rsrp:.1f} dBm.")
    if "sinr" in subset.columns:
        sinr = float(subset["sinr"].mean())
        parts.append(f"Mean SINR at failure: {sinr:.1f} dB.")
    if "rsrq" in subset.columns:
        rsrq = float(subset["rsrq"].mean())
        parts.append(f"Mean RSRQ at failure: {rsrq:.1f} dB.")
    return " ".join(parts)


def diagnose_handover(
    cell_id: str | None = None,
    query: str = "",
    csv_path: str | Path | None = None,
) -> dict[str, Any]:
    """Convenience API — returns {failure_type, root_cause, confidence}."""
    return HandoverFailureAgent().analyze(cell_id=cell_id, query=query, csv_path=csv_path).to_dict()
