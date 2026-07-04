"""5G Radio Link Failure (RLF) Agent — analyzes rlf_events.csv for mobility RCA."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from tnic.datasets.loaders import load_rlf_events

# Internal classification codes
RLF_CODES = frozenset({
    "COVERAGE_HOLE",
    "INTERFERENCE",
    "POST_HO_RLF",
    "RADIO_FAILURE",
})

RLF_LABELS: dict[str, str] = {
    "COVERAGE_HOLE": "Coverage Hole",
    "INTERFERENCE": "Interference",
    "POST_HO_RLF": "Post-HO RLF",
    "RADIO_FAILURE": "Radio Failure",
}

# CSV cause column -> internal code
CAUSE_MAP: dict[str, str] = {
    "COVERAGE": "COVERAGE_HOLE",
    "INTERFERENCE": "INTERFERENCE",
    "POST_HO": "POST_HO_RLF",
    "NONE": "RADIO_FAILURE",
}

ROOT_CAUSES: dict[str, str] = {
    "COVERAGE_HOLE": (
        "RLF due to coverage hole — RSRP below cell-edge threshold; UE lost DL sync "
        "before reestablishment could complete."
    ),
    "INTERFERENCE": (
        "RLF due to interference — adequate RSRP but SINR collapsed; dominant interferer "
        "or co-channel loading degraded PHY sync."
    ),
    "POST_HO_RLF": (
        "RLF after handover — target cell could not sustain the connection post-HO; "
        "often too-late HO or weak target SINR within 5 s of mobility."
    ),
    "RADIO_FAILURE": (
        "RLF due to radio/sync failure — consecutive out-of-sync indications (N310) "
        "expired T310 timer before RRC recovery."
    ),
}

BASE_CONFIDENCE: dict[str, float] = {
    "COVERAGE_HOLE": 0.84,
    "INTERFERENCE": 0.79,
    "POST_HO_RLF": 0.81,
    "RADIO_FAILURE": 0.77,
}

QUERY_HINTS: dict[str, str] = {
    "coverage hole": "COVERAGE_HOLE",
    "coverage": "COVERAGE_HOLE",
    "interference": "INTERFERENCE",
    "post-ho": "POST_HO_RLF",
    "post ho": "POST_HO_RLF",
    "after handover": "POST_HO_RLF",
    "after ho": "POST_HO_RLF",
    "radio failure": "RADIO_FAILURE",
    "n310": "RADIO_FAILURE",
    "t310": "RADIO_FAILURE",
    "out of sync": "RADIO_FAILURE",
    "sync fail": "RADIO_FAILURE",
}

# 3GPP typical NR threshold: N310 consecutive out-of-sync before T310 expiry
N310_RL_FAILURE_THRESHOLD = 4


@dataclass(frozen=True)
class RLFDiagnosis:
    """Structured RLF diagnosis."""

    rlf_type: str
    root_cause: str
    confidence: float
    cell_id: str | None = None
    evidence: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rlf_type": self.rlf_type,
            "root_cause": self.root_cause,
            "confidence": round(self.confidence, 2),
        }


class RLFAgent:
    """Telecom-grade 5G RLF analyzer over rlf_events.csv."""

    name = "rlf_agent"

    def analyze(
        self,
        cell_id: str | None = None,
        query: str = "",
        events: pd.DataFrame | None = None,
        csv_path: str | Path | None = None,
    ) -> RLFDiagnosis:
        df = self._load_events(events, csv_path)
        if cell_id:
            df = df[df["cell_id"] == cell_id]
        if df.empty:
            return RLFDiagnosis(
                rlf_type="No Data",
                root_cause="No RLF events found for the requested scope.",
                confidence=0.0,
                cell_id=cell_id,
            )

        enriched = _enrich_events(df)
        labeled = enriched[enriched["rlf_code"].isin(RLF_CODES)]
        if labeled.empty:
            return RLFDiagnosis(
                rlf_type="No RLF",
                root_cause="No actionable RLF signatures in event data.",
                confidence=0.5,
                cell_id=cell_id or str(df["cell_id"].mode().iloc[0]),
            )

        counts = labeled["rlf_code"].value_counts()
        hinted = _rlf_from_query(query)
        code = hinted if hinted else str(counts.index[0])
        subset = labeled[labeled["rlf_code"] == code]
        if subset.empty and hinted:
            subset = labeled.head(3)
            confidence = round(min(BASE_CONFIDENCE.get(code, 0.65), 0.75), 2)
        else:
            confidence = _score_confidence(code, counts, subset, len(enriched))
        evidence = _build_evidence(labeled, subset if not subset.empty else labeled, code)
        root = _root_cause_with_rf(code, subset if not subset.empty else labeled.head(3))

        return RLFDiagnosis(
            rlf_type=RLF_LABELS.get(code, code),
            root_cause=root,
            confidence=confidence,
            cell_id=cell_id or str(labeled["cell_id"].mode().iloc[0]),
            evidence=evidence,
        )

    def analyze_kpis(self, kpis: dict[str, Any], query: str = "") -> RLFDiagnosis:
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
            df = load_rlf_events()
        df.columns = [c.strip().lower() for c in df.columns]
        return df


def derive_n310(rsrp: float, sinr: float) -> int:
    """Estimate N310 out-of-sync indication count from RF at RLF (when UE log unavailable)."""
    if sinr >= 8:
        return 0
    if sinr <= -10:
        return 6
    if sinr <= 0:
        return 4
    if rsrp <= -118:
        return 5
    if rsrp <= -110:
        return 3
    return 1


def derive_t310_expired(rsrp: float, sinr: float, n310: int) -> bool:
    """True when T310 would expire (N310 consecutive out-of-sync per 3GPP NR)."""
    return n310 >= N310_RL_FAILURE_THRESHOLD or (sinr <= -8 and rsrp <= -112)


def classify_rlf_event(
    rsrp: float,
    sinr: float,
    cause: str | None = None,
    n310: int | None = None,
    t310_expired: bool | None = None,
) -> str:
    """Classify a single RLF event using RSRP, SINR, N310, T310, and optional CSV cause."""
    n310_val = n310 if n310 is not None else derive_n310(rsrp, sinr)
    t310_val = t310_expired if t310_expired is not None else derive_t310_expired(rsrp, sinr, n310_val)

    labeled = str(cause or "").strip().upper().replace(" ", "_")
    if labeled in CAUSE_MAP and labeled not in ("NONE", ""):
        mapped = CAUSE_MAP[labeled]
        if mapped == "POST_HO_RLF":
            return "POST_HO_RLF"
        if mapped == "COVERAGE_HOLE" or rsrp <= -110:
            return "COVERAGE_HOLE"
        if mapped == "INTERFERENCE":
            return "INTERFERENCE"

    if t310_val or n310_val >= N310_RL_FAILURE_THRESHOLD:
        return "RADIO_FAILURE"
    if rsrp <= -110:
        return "COVERAGE_HOLE"
    if cause == "Post_HO" or labeled == "POST_HO":
        return "POST_HO_RLF"
    if sinr <= 0 and rsrp > -110:
        return "INTERFERENCE"
    if sinr < 5:
        return "INTERFERENCE"
    return "RADIO_FAILURE"


def _enrich_events(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    n310_vals: list[int] = []
    t310_vals: list[bool] = []
    codes: list[str] = []

    for row in out.itertuples(index=False):
        rsrp = float(getattr(row, "rsrp", -999))
        sinr = float(getattr(row, "sinr", 0))
        cause = getattr(row, "cause", None)
        n310_raw = getattr(row, "n310", None) if hasattr(row, "n310") else None
        t310_raw = getattr(row, "t310", None) if hasattr(row, "t310") else None

        n310 = int(n310_raw) if n310_raw is not None and pd.notna(n310_raw) else derive_n310(rsrp, sinr)
        t310_exp = bool(t310_raw) if t310_raw is not None and pd.notna(t310_raw) else derive_t310_expired(rsrp, sinr, n310)

        n310_vals.append(n310)
        t310_vals.append(t310_exp)
        codes.append(classify_rlf_event(rsrp, sinr, cause, n310, t310_exp))

    out["n310"] = n310_vals
    out["t310_expired"] = t310_vals
    out["rlf_code"] = codes
    return out


def _rlf_from_query(query: str) -> str | None:
    ql = query.lower()
    for hint, code in sorted(QUERY_HINTS.items(), key=lambda x: len(x[0]), reverse=True):
        if hint in ql:
            return code
    return None


def _build_evidence(all_labeled: pd.DataFrame, subset: pd.DataFrame, code: str) -> dict[str, Any]:
    total = len(all_labeled)
    type_n = len(subset)
    ev: dict[str, Any] = {
        "rlf_code": code,
        "rlf_count": int(type_n),
        "total_rlf_events": int(total),
        "rlf_share_pct": round(100.0 * type_n / total, 2) if total else 0.0,
        "rlf_distribution": all_labeled["rlf_code"].value_counts().to_dict(),
    }
    for col in ("rsrp", "sinr", "n310"):
        if col in subset.columns and not subset.empty:
            ev[f"mean_{col}"] = round(float(subset[col].mean()), 2)
    if "t310_expired" in subset.columns and not subset.empty:
        ev["t310_expiry_pct"] = round(100.0 * float(subset["t310_expired"].sum()) / len(subset), 2)
    return ev


def _score_confidence(
    code: str,
    counts: pd.Series,
    subset: pd.DataFrame,
    total_events: int,
) -> float:
    base = BASE_CONFIDENCE.get(code, 0.70)
    type_count = int(counts.get(code, 0))
    dominance = type_count / int(counts.sum()) if counts.sum() else 0.0
    rate = type_count / total_events if total_events else 0.0
    score = base * 0.45 + dominance * 0.35 + min(rate * 5.0, 1.0) * 0.20

    if subset.empty:
        return round(min(max(score, 0.35), 0.95), 2)

    rsrp = float(subset["rsrp"].mean())
    sinr = float(subset["sinr"].mean())
    n310 = float(subset["n310"].mean())

    if code == "COVERAGE_HOLE" and rsrp <= -110:
        score += 0.06
    elif code == "INTERFERENCE" and sinr <= 0 and rsrp > -110:
        score += 0.06
    elif code == "POST_HO_RLF" and -105 <= rsrp <= -95:
        score += 0.04
    elif code == "RADIO_FAILURE" and n310 >= N310_RL_FAILURE_THRESHOLD:
        score += 0.07

    return round(min(max(score, 0.35), 0.95), 2)


def _root_cause_with_rf(code: str, subset: pd.DataFrame) -> str:
    base = ROOT_CAUSES.get(code, "Radio link failure detected — review RF and mobility logs.")
    if subset.empty:
        return base
    parts = [base]
    rsrp = float(subset["rsrp"].mean())
    sinr = float(subset["sinr"].mean())
    n310 = int(round(float(subset["n310"].mean())))
    t310_pct = 100.0 * float(subset["t310_expired"].sum()) / len(subset) if "t310_expired" in subset.columns else 0.0
    parts.append(f"Mean RSRP: {rsrp:.1f} dBm; mean SINR: {sinr:.1f} dB.")
    parts.append(f"Estimated N310: {n310}; T310 expiry on {t310_pct:.0f}% of events.")
    return " ".join(parts)


def diagnose_rlf(
    cell_id: str | None = None,
    query: str = "",
    csv_path: str | Path | None = None,
) -> dict[str, Any]:
    """Convenience API — returns {rlf_type, root_cause, confidence}."""
    return RLFAgent().analyze(cell_id=cell_id, query=query, csv_path=csv_path).to_dict()
