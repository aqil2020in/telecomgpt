"""5G Beamforming Agent — analyzes beam KPIs for massive MIMO / SSB RCA."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from tnic.datasets.loaders import (
    load_handover_events,
    load_pm_counters,
    load_rlf_events,
    load_throughput_metrics,
)

ISSUE_CODES = frozenset({
    "BEAM_CONGESTION",
    "BEAM_INSTABILITY",
    "BEAM_COVERAGE_HOLE",
    "BEAM_IMBALANCE",
})

ISSUE_LABELS: dict[str, str] = {
    "BEAM_CONGESTION": "Beam Congestion",
    "BEAM_INSTABILITY": "Beam Instability",
    "BEAM_COVERAGE_HOLE": "Beam Coverage Hole",
    "BEAM_IMBALANCE": "Beam Imbalance",
}

ROOT_CAUSES: dict[str, str] = {
    "BEAM_CONGESTION": (
        "Single or few SSB beams over-utilized — PRB/load concentrated on hot beams; "
        "UEs on congested beams see throughput collapse."
    ),
    "BEAM_INSTABILITY": (
        "Excessive beam switches with unstable SINR — beam management timers or "
        "SSB-RSRP hysteresis too aggressive for UE mobility profile."
    ),
    "BEAM_COVERAGE_HOLE": (
        "Beam footprint gap — RSRP below threshold on beam index; geo hole between "
        "SSB beam directions or tilt mis-pointing."
    ),
    "BEAM_IMBALANCE": (
        "Uneven traffic distribution across SSB beams — load ratio exceeds balance "
        "threshold; AAU calibration or weight drift suspected."
    ),
}

BASE_CONFIDENCE: dict[str, float] = {
    "BEAM_CONGESTION": 0.76,
    "BEAM_INSTABILITY": 0.80,
    "BEAM_COVERAGE_HOLE": 0.78,
    "BEAM_IMBALANCE": 0.73,
}

QUERY_HINTS: dict[str, str] = {
    "beam congestion": "BEAM_CONGESTION",
    "congested beam": "BEAM_CONGESTION",
    "beam overload": "BEAM_CONGESTION",
    "beam instability": "BEAM_INSTABILITY",
    "beam switch": "BEAM_INSTABILITY",
    "frequent switch": "BEAM_INSTABILITY",
    "beam coverage hole": "BEAM_COVERAGE_HOLE",
    "coverage hole": "BEAM_COVERAGE_HOLE",
    "beam gap": "BEAM_COVERAGE_HOLE",
    "beam imbalance": "BEAM_IMBALANCE",
    "uneven beam": "BEAM_IMBALANCE",
    "load imbalance": "BEAM_IMBALANCE",
}

NUM_SSB_BEAMS = 8
IMBALANCE_RATIO_THRESHOLD = 2.5


@dataclass(frozen=True)
class BeamDiagnosis:
    """Structured beamforming diagnosis."""

    issue_class: str
    root_cause: str
    confidence: float
    cell_id: str | None = None
    metrics: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "issue_class": self.issue_class,
            "root_cause": self.root_cause,
            "confidence": round(self.confidence, 2),
        }
        if self.metrics:
            out["metrics"] = self.metrics
        return out


class BeamformingAgent:
    """Telecom-grade beam analyzer using beam metrics (CSV or synthesized from RF datasets)."""

    name = "beamforming_agent"

    def analyze(
        self,
        cell_id: str | None = None,
        query: str = "",
        beams: pd.DataFrame | None = None,
        csv_path: str | Path | None = None,
    ) -> BeamDiagnosis:
        df = self._load_beams(beams, csv_path, cell_id)
        if cell_id and not df.empty and "cell_id" in df.columns:
            df = df[df["cell_id"] == cell_id]
        if df.empty:
            return BeamDiagnosis(
                issue_class="No Data",
                root_cause="No beam metrics found for the requested scope.",
                confidence=0.0,
                cell_id=cell_id,
            )

        enriched = _enrich_beams(df)
        if enriched.empty:
            return BeamDiagnosis(
                issue_class="No Issue",
                root_cause="Beam KPIs within normal bounds — no dominant beam issue detected.",
                confidence=0.55,
                cell_id=cell_id or str(df["cell_id"].mode().iloc[0]),
                metrics=_aggregate_metrics(enriched),
            )

        counts = enriched["issue_code"].value_counts()
        hinted = _issue_from_query(query)
        code = hinted if hinted else str(counts.index[0])
        subset = enriched[enriched["issue_code"] == code]
        if subset.empty and hinted:
            subset = enriched.head(3)
            confidence = round(min(BASE_CONFIDENCE.get(code, 0.65), 0.75), 2)
        else:
            confidence = _score_confidence(code, counts, subset, len(enriched))

        agg = _aggregate_metrics(subset if not subset.empty else enriched)
        root = _format_root_cause(code, agg, counts)
        evidence = _build_evidence(enriched, subset if not subset.empty else enriched, code)

        return BeamDiagnosis(
            issue_class=ISSUE_LABELS.get(code, code),
            root_cause=root,
            confidence=confidence,
            cell_id=cell_id or str(enriched["cell_id"].mode().iloc[0]),
            metrics=agg,
            evidence=evidence,
        )

    def analyze_kpis(self, kpis: dict[str, Any], query: str = "") -> BeamDiagnosis:
        cell_id = kpis.get("cell_id")
        if cell_id:
            return self.analyze(cell_id=str(cell_id), query=query)
        return self.analyze(query=query)

    def _load_beams(
        self,
        beams: pd.DataFrame | None,
        csv_path: str | Path | None,
        cell_id: str | None,
    ) -> pd.DataFrame:
        if beams is not None:
            df = beams.copy()
        elif csv_path is not None:
            df = pd.read_csv(csv_path)
        elif cell_id:
            df = synthesize_beam_metrics(cell_id)
        else:
            df = pd.DataFrame()
        df.columns = [c.strip().lower() for c in df.columns]
        return _normalize_columns(df)


def synthesize_beam_metrics(cell_id: str, num_beams: int = NUM_SSB_BEAMS) -> pd.DataFrame:
    """Build per-SSB beam metrics from handover, RLF, and throughput datasets."""
    ho = load_handover_events()
    ho_cell = ho[ho["cell_id"] == cell_id] if "cell_id" in ho.columns else ho.iloc[0:0]
    rlf = load_rlf_events()
    rlf_cell = rlf[rlf["cell_id"] == cell_id] if "cell_id" in rlf.columns else rlf.iloc[0:0]
    tp = load_throughput_metrics()
    tp_cell = tp[tp["cell_id"] == cell_id] if "cell_id" in tp.columns else tp.iloc[0:0]

    base_rsrp = float(ho_cell["rsrp"].mean()) if not ho_cell.empty else -102.0
    base_sinr = float(ho_cell["sinr"].mean()) if not ho_cell.empty else 8.0
    base_prb = float(tp_cell["prb_util"].mean()) if not tp_cell.empty else 55.0
    rlf_count = len(rlf_cell)

    try:
        cell_num = int("".join(c for c in cell_id if c.isdigit()) or "401")
    except ValueError:
        cell_num = 401
    tier = "bad" if cell_num <= 404 else "medium" if cell_num <= 408 else "good"

    rows: list[dict[str, Any]] = []
    for beam_idx in range(num_beams):
        edge = beam_idx in (0, num_beams - 1)
        center = abs(beam_idx - (num_beams - 1) / 2) < 1.5

        util_base = base_prb * (1.35 if center else 0.85 if edge else 1.0)
        if tier == "bad":
            util_base *= 1.15 if center else 0.9
        elif tier == "good":
            util_base *= 0.85

        beam_util = min(98.0, max(8.0, util_base + beam_idx * 2.5))
        switches = int(6 + beam_idx * 1.2 + rlf_count / 25)
        if tier == "bad":
            switches += 6 if edge else 3
        if tier == "medium" and edge:
            switches += 4

        rsrp_offset = (beam_idx - (num_beams - 1) / 2) * 2.8
        rsrp = base_rsrp + rsrp_offset - (8 if edge and tier == "bad" else 0)
        sinr = base_sinr - abs(beam_idx - (num_beams - 1) / 2) * 1.1 - (3 if edge else 0)

        rows.append({
            "cell_id": cell_id,
            "beam_index": beam_idx,
            "beam_utilization": round(beam_util, 1),
            "beam_switches": switches,
            "rsrp": round(rsrp, 1),
            "sinr": round(sinr, 1),
        })

    return pd.DataFrame(rows)


def classify_beam_issue(
    beam_util: float,
    beam_switches: float,
    rsrp: float,
    sinr: float,
    imbalance_ratio: float | None = None,
) -> str:
    """Classify beam issue from utilization, switches, and RF."""
    if imbalance_ratio is not None and imbalance_ratio >= IMBALANCE_RATIO_THRESHOLD:
        return "BEAM_IMBALANCE"
    if rsrp <= -110:
        return "BEAM_COVERAGE_HOLE"
    if beam_util >= 85:
        return "BEAM_CONGESTION"
    if beam_switches >= 12 and sinr < 8:
        return "BEAM_INSTABILITY"
    if beam_switches >= 15:
        return "BEAM_INSTABILITY"
    if beam_util >= 70 and sinr >= 10:
        return "BEAM_CONGESTION"
    return "BEAM_INSTABILITY" if beam_switches >= 10 else "BEAM_CONGESTION"


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    renames = {
        "beam_util": "beam_utilization",
        "beam_idx": "beam_index",
        "utilization": "beam_utilization",
        "switches": "beam_switches",
        "switch_count": "beam_switches",
    }
    for old, new in renames.items():
        if old in out.columns and new not in out.columns:
            out = out.rename(columns={old: new})
    return out


def _imbalance_ratio(util_series: pd.Series) -> float:
    if util_series.empty:
        return 1.0
    hi = float(util_series.max())
    lo = float(util_series.min())
    if lo <= 0:
        return hi
    return round(hi / lo, 2)


def _enrich_beams(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    ratio = _imbalance_ratio(out["beam_utilization"]) if "beam_utilization" in out.columns else 1.0
    codes: list[str] = []
    for row in out.itertuples(index=False):
        util = float(getattr(row, "beam_utilization", 50))
        switches = float(getattr(row, "beam_switches", 5))
        rsrp = float(getattr(row, "rsrp", -100))
        sinr = float(getattr(row, "sinr", 10))
        codes.append(classify_beam_issue(util, switches, rsrp, sinr, ratio))
    out["issue_code"] = codes
    if ratio >= IMBALANCE_RATIO_THRESHOLD:
        out.loc[out["beam_utilization"] == out["beam_utilization"].max(), "issue_code"] = "BEAM_IMBALANCE"
    return out


def _aggregate_metrics(df: pd.DataFrame) -> dict[str, Any]:
    def mean_col(name: str) -> float | None:
        if name not in df.columns or df.empty:
            return None
        return round(float(df[name].mean()), 2)

    peak_beam = None
    if "beam_index" in df.columns and "beam_utilization" in df.columns and not df.empty:
        peak_beam = int(df.loc[df["beam_utilization"].idxmax(), "beam_index"])

    return {
        "beam_utilization": mean_col("beam_utilization"),
        "beam_index": peak_beam if peak_beam is not None else mean_col("beam_index"),
        "beam_switches": mean_col("beam_switches"),
        "sinr": mean_col("sinr"),
        "rsrp": mean_col("rsrp"),
        "beam_imbalance_ratio": _imbalance_ratio(df["beam_utilization"]) if "beam_utilization" in df.columns else None,
    }


def _issue_from_query(query: str) -> str | None:
    ql = query.lower()
    for hint, code in sorted(QUERY_HINTS.items(), key=lambda x: len(x[0]), reverse=True):
        if hint in ql:
            return code
    return None


def _build_evidence(all_rows: pd.DataFrame, subset: pd.DataFrame, code: str) -> dict[str, Any]:
    return {
        "issue_code": code,
        "issue_class": ISSUE_LABELS.get(code, code),
        "beam_count": int(len(all_rows)),
        "affected_beams": int(len(subset)),
        "issue_share_pct": round(100.0 * len(subset) / len(all_rows), 2) if len(all_rows) else 0.0,
        "issue_distribution": {
            ISSUE_LABELS.get(k, k): int(v)
            for k, v in all_rows["issue_code"].value_counts().items()
        },
        "peak_beam_index": int(all_rows.loc[all_rows["beam_utilization"].idxmax(), "beam_index"])
        if "beam_utilization" in all_rows.columns and not all_rows.empty else None,
    }


def _score_confidence(
    code: str,
    counts: pd.Series,
    subset: pd.DataFrame,
    total: int,
) -> float:
    base = BASE_CONFIDENCE.get(code, 0.72)
    type_count = int(counts.get(code, 0))
    dominance = type_count / total if total else 0.0
    score = base * 0.55 + dominance * 0.45
    if not subset.empty:
        if code == "BEAM_COVERAGE_HOLE" and float(subset["rsrp"].mean()) <= -110:
            score += 0.05
        if code == "BEAM_CONGESTION" and float(subset["beam_utilization"].mean()) >= 85:
            score += 0.05
        if code == "BEAM_INSTABILITY" and float(subset["beam_switches"].mean()) >= 12:
            score += 0.05
    return round(min(max(score, 0.40), 0.95), 2)


def _format_root_cause(code: str, metrics: dict[str, Any], counts: pd.Series) -> str:
    base = ROOT_CAUSES.get(code, "Beam issue detected — review SSB configuration and AAU calibration.")
    type_count = int(counts.get(code, 0))
    total = int(counts.sum())
    pct = round(100.0 * type_count / total, 1) if total else 0.0
    label = ISSUE_LABELS.get(code, code)
    detail = (
        f"Beam util {metrics.get('beam_utilization', '—')}%, "
        f"peak beam index {metrics.get('beam_index', '—')}, "
        f"switches {metrics.get('beam_switches', '—')}, "
        f"RSRP {metrics.get('rsrp', '—')} dBm, SINR {metrics.get('sinr', '—')} dB."
    )
    return f"{label}: {base} ({type_count}/{total} beams, {pct}% of beam issue mix). {detail}"


def diagnose_beamforming(
    cell_id: str | None = None,
    query: str = "",
    csv_path: str | Path | None = None,
) -> dict[str, Any]:
    """Convenience API — returns issue_class, root_cause, confidence, metrics."""
    return BeamformingAgent().analyze(cell_id=cell_id, query=query, csv_path=csv_path).to_dict()
