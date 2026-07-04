"""5G Throughput Analysis Agent — analyzes throughput_metrics.csv + PM counters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from tnic.datasets.loaders import load_pm_counters, load_throughput_metrics

ISSUE_CODES = frozenset({"CONGESTION", "RF_ISSUE", "SCHEDULER", "BACKHAUL"})

ISSUE_LABELS: dict[str, str] = {
    "CONGESTION": "Congestion",
    "RF_ISSUE": "RF Issue",
    "SCHEDULER": "Scheduler Issue",
    "BACKHAUL": "Backhaul Issue",
}

CSV_ISSUE_MAP: dict[str, str] = {
    "CONGESTION": "CONGESTION",
    "RF": "RF_ISSUE",
    "SCHEDULER": "SCHEDULER",
    "BACKHAUL": "BACKHAUL",
}

ROOT_CAUSES: dict[str, str] = {
    "CONGESTION": (
        "Scheduler congestion — PRB utilization saturated; UEs competing for limited "
        "air-time despite acceptable CQI."
    ),
    "RF_ISSUE": (
        "RF-limited throughput — low CQI and/or high BLER; radio quality caps MCS "
        "selection and effective code rate."
    ),
    "SCHEDULER": (
        "Scheduler allocation issue — PRB loading and MCS/CQI mismatch; scheduler "
        "not assigning RBs efficiently to capable UEs."
    ),
    "BACKHAUL": (
        "Backhaul/transport bottleneck — good RF (CQI) but DL throughput capped below "
        "expected; N3/F1 or transport link likely saturated."
    ),
}

BASE_CONFIDENCE: dict[str, float] = {
    "CONGESTION": 0.71,
    "RF_ISSUE": 0.85,
    "SCHEDULER": 0.73,
    "BACKHAUL": 0.75,
}

QUERY_HINTS: dict[str, str] = {
    "congestion": "CONGESTION",
    "prb util": "CONGESTION",
    "scheduler congestion": "CONGESTION",
    "rf issue": "RF_ISSUE",
    "low cqi": "RF_ISSUE",
    "high bler": "RF_ISSUE",
    "radio limited": "RF_ISSUE",
    "scheduler issue": "SCHEDULER",
    "scheduler": "SCHEDULER",
    "backhaul issue": "BACKHAUL",
    "backhaul": "BACKHAUL",
    "transport bottleneck": "BACKHAUL",
    "n3 bottleneck": "BACKHAUL",
}


@dataclass(frozen=True)
class ThroughputDiagnosis:
    """Structured throughput issue diagnosis."""

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


class ThroughputAnalysisAgent:
    """Telecom-grade throughput analyzer over throughput_metrics.csv."""

    name = "throughput_agent"

    def analyze(
        self,
        cell_id: str | None = None,
        query: str = "",
        metrics: pd.DataFrame | None = None,
        csv_path: str | Path | None = None,
    ) -> ThroughputDiagnosis:
        df = self._load_metrics(metrics, csv_path)
        if cell_id and not df.empty and "cell_id" in df.columns:
            df = df[df["cell_id"] == cell_id]
        if df.empty:
            return ThroughputDiagnosis(
                issue_class="No Data",
                root_cause="No throughput metrics found for the requested scope.",
                confidence=0.0,
                cell_id=cell_id,
            )

        enriched = _enrich_metrics(df, cell_id)
        classified = enriched[enriched["issue_code"].isin(ISSUE_CODES)]
        if classified.empty:
            return ThroughputDiagnosis(
                issue_class="No Issue",
                root_cause="Throughput metrics within normal bounds — no dominant issue class detected.",
                confidence=0.55,
                cell_id=cell_id or str(df["cell_id"].mode().iloc[0]),
                metrics=_aggregate_metrics(enriched),
            )

        counts = classified["issue_code"].value_counts()
        hinted = _issue_from_query(query)
        code = hinted if hinted else str(counts.index[0])
        subset = classified[classified["issue_code"] == code]
        if subset.empty and hinted:
            confidence = round(min(BASE_CONFIDENCE.get(code, 0.65), 0.75), 2)
            subset = classified.head(3)
        else:
            confidence = _score_confidence(code, counts, subset, len(classified))

        agg = _aggregate_metrics(subset if not subset.empty else classified)
        root = _format_root_cause(code, agg, counts, code)
        evidence = _build_evidence(classified, subset if not subset.empty else classified, code)

        return ThroughputDiagnosis(
            issue_class=ISSUE_LABELS.get(code, code),
            root_cause=root,
            confidence=confidence,
            cell_id=cell_id or str(classified["cell_id"].mode().iloc[0]),
            metrics=agg,
            evidence=evidence,
        )

    def analyze_kpis(self, kpis: dict[str, Any], query: str = "") -> ThroughputDiagnosis:
        cell_id = kpis.get("cell_id")
        if cell_id:
            return self.analyze(cell_id=str(cell_id), query=query)
        return self.analyze(query=query)

    def _load_metrics(
        self,
        metrics: pd.DataFrame | None,
        csv_path: str | Path | None,
    ) -> pd.DataFrame:
        if metrics is not None:
            df = metrics.copy()
        elif csv_path is not None:
            df = pd.read_csv(csv_path)
        else:
            df = load_throughput_metrics()
        df.columns = [c.strip().lower() for c in df.columns]
        return df


def derive_mcs(cqi: float, sinr: float | None = None) -> float:
    """Estimate DL MCS from CQI (and optional SINR) when UE reports unavailable."""
    base = max(0.0, min(28.0, cqi * 1.85 - 2.0))
    if sinr is not None and sinr < 5:
        base = max(0.0, base - 3.0)
    return round(base, 1)


def derive_bler(cqi: float, prb_util: float, sinr: float | None = None) -> float:
    """Estimate DL BLER (%) from CQI/PRB when MAC BLER counters unavailable."""
    bler = max(0.1, (12.0 - cqi) * 2.2)
    if prb_util >= 85:
        bler += 3.0
    if sinr is not None and sinr < 0:
        bler += 5.0
    return round(min(max(bler, 0.1), 35.0), 2)


def expected_dl_throughput_mbps(cqi: float, prb_util: float) -> float:
    """Rough expected DL Mbps given CQI and load (for backhaul detection)."""
    base = max(30.0, cqi * 45.0)
    load_factor = max(0.35, 1.0 - prb_util / 120.0)
    return round(base * load_factor, 1)


def classify_throughput_issue(
    cqi: float,
    mcs: float,
    prb_util: float,
    bler: float,
    dl_tp: float,
    ul_tp: float | None = None,
    labeled_issue: str | None = None,
) -> str:
    """Classify throughput bottleneck using CQI, MCS, PRB, BLER, and throughput."""
    if labeled_issue:
        key = str(labeled_issue).strip().upper()
        if key in CSV_ISSUE_MAP and key != "NONE":
            mapped = CSV_ISSUE_MAP[key]
            if mapped == "RF_ISSUE" or (cqi <= 6 or bler >= 12):
                return "RF_ISSUE" if cqi <= 8 or bler >= 10 else mapped
            return mapped

    expected = expected_dl_throughput_mbps(cqi, prb_util)
    if prb_util >= 82:
        return "CONGESTION"
    if cqi <= 6 or bler >= 12:
        return "RF_ISSUE"
    if cqi >= 8 and dl_tp < expected * 0.55:
        return "BACKHAUL"
    if 50 <= prb_util <= 88 and mcs < derive_mcs(cqi) * 0.75:
        return "SCHEDULER"
    if bler >= 8 and cqi < 9:
        return "RF_ISSUE"
    if ul_tp is not None and ul_tp < dl_tp * 0.05 and cqi >= 10:
        return "BACKHAUL"
    return "SCHEDULER"


def _enrich_metrics(df: pd.DataFrame, cell_id: str | None) -> pd.DataFrame:
    out = df.copy()
    ul_by_cell = _ul_throughput_by_cell(cell_id)

    sinr_col = "sinr" if "sinr" in out.columns else None
    mcs_vals: list[float] = []
    bler_vals: list[float] = []
    ul_vals: list[float | None] = []
    codes: list[str] = []

    for row in out.itertuples(index=False):
        cqi = float(getattr(row, "cqi", 8))
        prb = float(getattr(row, "prb_util", 50))
        dl = float(getattr(row, "dl_tp", 100))
        sinr = float(getattr(row, sinr_col)) if sinr_col and pd.notna(getattr(row, sinr_col, None)) else None
        issue = getattr(row, "issue", None)
        cid = getattr(row, "cell_id", None)

        mcs_raw = getattr(row, "mcs", None) if hasattr(row, "mcs") else None
        bler_raw = getattr(row, "bler", None) if hasattr(row, "bler") else None
        ul_raw = getattr(row, "ul_tp", None) if hasattr(row, "ul_tp") else None

        mcs = float(mcs_raw) if mcs_raw is not None and pd.notna(mcs_raw) else derive_mcs(cqi, sinr)
        bler = float(bler_raw) if bler_raw is not None and pd.notna(bler_raw) else derive_bler(cqi, prb, sinr)
        ul = float(ul_raw) if ul_raw is not None and pd.notna(ul_raw) else ul_by_cell.get(str(cid))

        mcs_vals.append(mcs)
        bler_vals.append(bler)
        ul_vals.append(ul)
        codes.append(classify_throughput_issue(cqi, mcs, prb, bler, dl, ul, issue))

    out["mcs"] = mcs_vals
    out["bler"] = bler_vals
    out["ul_tp"] = ul_vals
    out["issue_code"] = codes
    return out


def _ul_throughput_by_cell(cell_filter: str | None) -> dict[str, float]:
    try:
        pm = load_pm_counters()
        if cell_filter:
            pm = pm[pm["cell_id"] == cell_filter]
        if pm.empty or "ul_tp" not in pm.columns:
            return {}
        return pm.groupby("cell_id")["ul_tp"].mean().to_dict()
    except (FileNotFoundError, KeyError):
        return {}


def _aggregate_metrics(df: pd.DataFrame) -> dict[str, Any]:
    def mean_col(name: str) -> float | None:
        if name not in df.columns or df.empty:
            return None
        return round(float(df[name].mean()), 2)

    dl = mean_col("dl_tp")
    ul = mean_col("ul_tp")
    return {
        "cqi": mean_col("cqi"),
        "mcs": mean_col("mcs"),
        "prb_utilization": mean_col("prb_util"),
        "bler": mean_col("bler"),
        "dl_throughput_mbps": dl,
        "ul_throughput_mbps": ul,
    }


def _issue_from_query(query: str) -> str | None:
    ql = query.lower()
    for hint, code in sorted(QUERY_HINTS.items(), key=lambda x: len(x[0]), reverse=True):
        if hint in ql:
            return code
    return None


def _build_evidence(all_rows: pd.DataFrame, subset: pd.DataFrame, code: str) -> dict[str, Any]:
    total = len(all_rows)
    type_n = len(subset)
    return {
        "issue_code": code,
        "issue_class": ISSUE_LABELS.get(code, code),
        "sample_count": int(type_n),
        "total_samples": int(total),
        "issue_share_pct": round(100.0 * type_n / total, 2) if total else 0.0,
        "issue_distribution": {
            ISSUE_LABELS.get(k, k): int(v)
            for k, v in all_rows["issue_code"].value_counts().items()
        },
    }


def _score_confidence(
    code: str,
    counts: pd.Series,
    subset: pd.DataFrame,
    total: int,
) -> float:
    base = BASE_CONFIDENCE.get(code, 0.70)
    type_count = int(counts.get(code, 0))
    dominance = type_count / int(counts.sum()) if counts.sum() else 0.0
    rate = type_count / total if total else 0.0
    score = base * 0.50 + dominance * 0.35 + min(rate * 4.0, 1.0) * 0.15

    if subset.empty:
        return round(min(max(score, 0.40), 0.95), 2)

    agg = _aggregate_metrics(subset)
    cqi = agg.get("cqi") or 99
    bler = agg.get("bler") or 0
    prb = agg.get("prb_utilization") or 0

    if code == "RF_ISSUE" and cqi <= 7 and bler >= 10:
        score += 0.06
    elif code == "CONGESTION" and prb >= 80:
        score += 0.06
    elif code == "BACKHAUL" and cqi >= 9:
        score += 0.04
    elif code == "SCHEDULER" and 50 <= prb <= 85:
        score += 0.04

    return round(min(max(score, 0.40), 0.95), 2)


def _format_root_cause(code: str, metrics: dict[str, Any], counts: pd.Series, _code_key: str) -> str:
    base = ROOT_CAUSES.get(code, "Throughput degradation detected — review RF and transport KPIs.")
    type_count = int(counts.get(code, 0))
    total = int(counts.sum())
    pct = round(100.0 * type_count / total, 1) if total else 0.0
    label = ISSUE_LABELS.get(code, code)
    m = metrics
    detail = (
        f"CQI {m.get('cqi', '—')}, MCS {m.get('mcs', '—')}, "
        f"PRB {m.get('prb_utilization', '—')}%, BLER {m.get('bler', '—')}%, "
        f"DL {m.get('dl_throughput_mbps', '—')} Mbps, UL {m.get('ul_throughput_mbps', '—')} Mbps."
    )
    return f"{label}: {base} ({type_count}/{total} samples, {pct}% of issue mix). Metrics — {detail}"


def diagnose_throughput(
    cell_id: str | None = None,
    query: str = "",
    csv_path: str | Path | None = None,
) -> dict[str, Any]:
    """Convenience API — returns issue_class, root_cause, confidence, metrics."""
    return ThroughputAnalysisAgent().analyze(cell_id=cell_id, query=query, csv_path=csv_path).to_dict()
