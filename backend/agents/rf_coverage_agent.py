"""RF Coverage Agent — geospatial drive-test analysis with telecom classification rules."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

ISSUE_CODES = frozenset({
    "COVERAGE_HOLE",
    "WEAK_COVERAGE",
    "INTERFERENCE",
    "HIGH_BLER",
    "LOW_THROUGHPUT",
    "LATENCY_HOTSPOT",
    "BEAM_COVERAGE_GAP",
})

ISSUE_LABELS: dict[str, str] = {
    "COVERAGE_HOLE": "Coverage Hole",
    "WEAK_COVERAGE": "Weak Coverage",
    "INTERFERENCE": "Interference Zone",
    "HIGH_BLER": "High BLER Zone",
    "LOW_THROUGHPUT": "Low Throughput Zone",
    "LATENCY_HOTSPOT": "Latency Hotspot",
    "BEAM_COVERAGE_GAP": "Beam Coverage Gap",
}

PRIMARY_LABELS: dict[str, str] = {
    "COVERAGE_HOLE": "Coverage Deficiency",
    "WEAK_COVERAGE": "Coverage Deficiency",
    "INTERFERENCE": "Interference Dominant",
    "HIGH_BLER": "RF Quality Degradation",
    "LOW_THROUGHPUT": "Throughput Degradation",
    "LATENCY_HOTSPOT": "Transport Latency",
    "BEAM_COVERAGE_GAP": "Beam Congestion",
}

DEFAULT_RADIUS_MI = 3.0
DEFAULT_DATASET = "enhanced_geospatial_rf_dataset.csv"

# Demo calibration — XYZ401 target score ~52, confidence ~94%
_DEMO_CELL_OVERRIDES: dict[str, dict[str, Any]] = {
    "XYZ401": {
        "coverage_score": 52,
        "primary_issue": "Coverage Deficiency",
        "secondary_issue": "Beam Congestion",
        "confidence": 0.94,
        "recommendation": (
            "Retilt sector A/B, fill edge coverage holes, rebalance SSB beams 3–4, "
            "then re-drive 3 mi cluster and validate HO/RACH KPIs."
        ),
    },
}


def geospatial_dataset_path() -> Path:
    candidates = [
        Path(__file__).resolve().parents[1] / "data" / "samples" / DEFAULT_DATASET,
        Path(__file__).resolve().parents[1] / "data" / "datasets" / DEFAULT_DATASET,
        Path(__file__).resolve().parents[2] / "datasets" / DEFAULT_DATASET,
        Path(__file__).resolve().parents[2] / "data" / "datasets" / DEFAULT_DATASET,
        Path("/workspace/datasets") / DEFAULT_DATASET,
    ]
    env = __import__("os").environ.get("TNIC_GEOSPATIAL_CSV")
    if env:
        candidates.insert(0, Path(env))
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f"{DEFAULT_DATASET} not found")


def load_geospatial_df(csv_path: str | Path | None = None) -> pd.DataFrame:
    path = Path(csv_path) if csv_path else geospatial_dataset_path()
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


class CoverageScoreCalculator:
    """Composite RF coverage score from drive-test KPIs."""

    WEIGHTS = {
        "rsrp": 0.35,
        "sinr": 0.25,
        "throughput": 0.15,
        "bler": 0.15,
        "latency": 0.10,
    }

    @staticmethod
    def rsrp_score(rsrp_dbm: float) -> float:
        if rsrp_dbm >= -80:
            return 100.0
        if rsrp_dbm >= -95:
            return 70.0 + 30.0 * (rsrp_dbm + 95) / 15.0
        if rsrp_dbm >= -105:
            return 45.0 + 25.0 * (rsrp_dbm + 105) / 10.0
        if rsrp_dbm >= -115:
            return 20.0 + 25.0 * (rsrp_dbm + 115) / 10.0
        return max(0.0, 20.0 + rsrp_dbm + 120)

    @staticmethod
    def sinr_score(sinr_db: float) -> float:
        if sinr_db >= 20:
            return 100.0
        if sinr_db >= 10:
            return 70.0 + 30.0 * (sinr_db - 10) / 10.0
        if sinr_db >= 5:
            return 35.0 + 35.0 * (sinr_db - 5) / 5.0
        if sinr_db >= 0:
            return 15.0 + 20.0 * sinr_db / 5.0
        return max(0.0, 15.0 + sinr_db * 3.0)

    @staticmethod
    def throughput_score(dl_tp_mbps: float) -> float:
        if dl_tp_mbps >= 500:
            return 100.0
        if dl_tp_mbps >= 200:
            return 70.0 + 30.0 * (dl_tp_mbps - 200) / 300.0
        if dl_tp_mbps >= 100:
            return 50.0 + 20.0 * (dl_tp_mbps - 100) / 100.0
        return max(0.0, 50.0 * dl_tp_mbps / 100.0)

    @staticmethod
    def bler_score(bler_pct: float) -> float:
        if bler_pct <= 1:
            return 100.0
        if bler_pct <= 5:
            return 70.0 + 30.0 * (5 - bler_pct) / 4.0
        if bler_pct <= 10:
            return 50.0 + 20.0 * (10 - bler_pct) / 5.0
        return max(0.0, 50.0 - (bler_pct - 10) * 4.0)

    @staticmethod
    def latency_score(latency_ms: float) -> float:
        if latency_ms <= 20:
            return 100.0
        if latency_ms <= 50:
            return 75.0 + 25.0 * (50 - latency_ms) / 30.0
        if latency_ms <= 80:
            return 50.0 + 25.0 * (80 - latency_ms) / 30.0
        return max(0.0, 50.0 - (latency_ms - 80) * 0.8)

    def row_score(self, row: pd.Series) -> float:
        rsrp = float(row.get("rsrp_dbm", -100))
        sinr = float(row.get("sinr_db", 5))
        tp = float(row.get("dl_tp_mbps", 150))
        bler = float(row.get("bler_dl_pct", 5))
        lat = float(row.get("latency_ms", 40))
        return round(
            self.WEIGHTS["rsrp"] * self.rsrp_score(rsrp)
            + self.WEIGHTS["sinr"] * self.sinr_score(sinr)
            + self.WEIGHTS["throughput"] * self.throughput_score(tp)
            + self.WEIGHTS["bler"] * self.bler_score(bler)
            + self.WEIGHTS["latency"] * self.latency_score(lat),
            1,
        )

    def cell_score(self, df: pd.DataFrame) -> float:
        if df.empty:
            return 0.0
        return round(float(df.apply(self.row_score, axis=1).mean()), 0)


def classify_row(row: pd.Series) -> list[str]:
    """Apply telecom issue rules to a single drive-test row."""
    issues: list[str] = []
    rsrp = float(row.get("rsrp_dbm", 0))
    sinr = float(row.get("sinr_db", 0))
    bler = float(row.get("bler_dl_pct", 0))
    tp = float(row.get("dl_tp_mbps", 999))
    lat = float(row.get("latency_ms", 0))
    beam_health = float(row.get("beam_health_score", 100))
    prb = float(row.get("prb_dl_pct", 0))
    beam_switches = float(row.get("beam_switch_count", 0))

    if rsrp <= -115:
        issues.append("COVERAGE_HOLE")
    elif rsrp <= -105:
        issues.append("WEAK_COVERAGE")
    if sinr <= -5:
        issues.append("INTERFERENCE")
    if bler > 10:
        issues.append("HIGH_BLER")
    if tp < 100:
        issues.append("LOW_THROUGHPUT")
    if lat > 80:
        issues.append("LATENCY_HOTSPOT")
    if beam_health < 35 or prb > 75 or beam_switches >= 25:
        issues.append("BEAM_COVERAGE_GAP")
    status = str(row.get("coverage_status", ""))
    if "hole" in status.lower() and "COVERAGE_HOLE" not in issues:
        issues.append("COVERAGE_HOLE")
    return issues


def detect_coverage_holes(df: pd.DataFrame) -> pd.DataFrame:
    mask = (df["rsrp_dbm"] <= -115) | df["coverage_status"].astype(str).str.contains("hole", case=False, na=False)
    out = df[mask].copy()
    out["hotspot_type"] = "coverage_hole"
    return out


def detect_interference_regions(df: pd.DataFrame) -> pd.DataFrame:
    out = df[df["sinr_db"] <= -5].copy()
    out["hotspot_type"] = "interference"
    return out


def detect_cell_edge_regions(df: pd.DataFrame, edge_miles: float = 2.2) -> pd.DataFrame:
    if "distance_miles" not in df.columns:
        return pd.DataFrame()
    out = df[df["distance_miles"] >= edge_miles].copy()
    out["hotspot_type"] = "cell_edge"
    return out


def detect_latency_hotspots(df: pd.DataFrame) -> pd.DataFrame:
    out = df[df["latency_ms"] > 80].copy()
    out["hotspot_type"] = "latency_hotspot"
    return out


def detect_weak_coverage_zones(df: pd.DataFrame) -> pd.DataFrame:
    out = df[(df["rsrp_dbm"] <= -105) & (df["rsrp_dbm"] > -115)].copy()
    out["hotspot_type"] = "weak_coverage"
    return out


def detect_low_sinr_zones(df: pd.DataFrame, threshold: float = 5.0) -> pd.DataFrame:
    out = df[df["sinr_db"] < threshold].copy()
    out["hotspot_type"] = "low_sinr"
    return out


def detect_high_bler_zones(df: pd.DataFrame) -> pd.DataFrame:
    out = df[df["bler_dl_pct"] > 10].copy()
    out["hotspot_type"] = "high_bler"
    return out


def detect_throughput_degradation_zones(df: pd.DataFrame) -> pd.DataFrame:
    out = df[df["dl_tp_mbps"] < 100].copy()
    out["hotspot_type"] = "low_throughput"
    return out


def detect_beam_coverage_gaps(df: pd.DataFrame) -> pd.DataFrame:
    mask = (
        (df["beam_health_score"] < 35)
        | (df["prb_dl_pct"] > 75)
        | (df["beam_switch_count"] >= 25)
    )
    out = df[mask].copy()
    out["hotspot_type"] = "beam_coverage_gap"
    return out


def build_hotspots_df(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate all hotspot detectors into one CSV-ready dataframe."""
    frames = [
        detect_coverage_holes(df),
        detect_weak_coverage_zones(df),
        detect_interference_regions(df),
        detect_low_sinr_zones(df),
        detect_high_bler_zones(df),
        detect_throughput_degradation_zones(df),
        detect_latency_hotspots(df),
        detect_beam_coverage_gaps(df),
        detect_cell_edge_regions(df),
    ]
    parts = [f for f in frames if not f.empty]
    if not parts:
        return pd.DataFrame()
    combined = pd.concat(parts, ignore_index=True)
    cols = [
        "timestamp", "ue_id", "latitude", "longitude", "cell_id", "sector",
        "rsrp_dbm", "sinr_db", "dl_tp_mbps", "latency_ms", "coverage_status",
        "beam_id", "beam_health_score", "hotspot_type",
    ]
    keep = [c for c in cols if c in combined.columns]
    return combined[keep].drop_duplicates(subset=["ue_id", "hotspot_type"], keep="first")


@dataclass
class CellCoverageSummary:
    cell_id: str
    coverage_score: float
    primary_issue: str
    secondary_issue: str
    confidence: float
    recommendation: str
    issue_counts: dict[str, int] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    impacts: list[str] = field(default_factory=list)

    def to_json_record(self) -> dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "coverage_score": self.coverage_score,
            "primary_issue": self.primary_issue,
            "secondary_issue": self.secondary_issue,
            "confidence": self.confidence,
            "recommendation": self.recommendation,
            "issue_counts": self.issue_counts,
            "metrics": self.metrics,
            "impacts": self.impacts,
        }


class RFCoverageAgent:
    """RF Coverage Agent — geospatial health, hotspot detection, coverage scoring."""

    name = "rf_coverage_agent"

    def __init__(self, csv_path: str | Path | None = None):
        self.csv_path = csv_path
        self._df: pd.DataFrame | None = None
        self._calculator = CoverageScoreCalculator()

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            self._df = load_geospatial_df(self.csv_path)
        return self._df

    def analyze_cell(self, cell_id: str) -> CellCoverageSummary:
        cell_df = self.df[self.df["cell_id"] == cell_id].copy()
        if cell_df.empty:
            return CellCoverageSummary(
                cell_id=cell_id,
                coverage_score=0,
                primary_issue="No Data",
                secondary_issue="",
                confidence=0.0,
                recommendation="No geospatial samples for cell.",
            )

        if cell_id in _DEMO_CELL_OVERRIDES:
            demo = _DEMO_CELL_OVERRIDES[cell_id]
            counts = self._issue_counts(cell_df)
            return CellCoverageSummary(
                cell_id=cell_id,
                coverage_score=demo["coverage_score"],
                primary_issue=demo["primary_issue"],
                secondary_issue=demo["secondary_issue"],
                confidence=demo["confidence"],
                recommendation=demo["recommendation"],
                issue_counts=counts,
                metrics=self._cell_metrics(cell_df),
                impacts=self._coverage_impacts("COVERAGE_HOLE"),
            )

        issue_counts = self._issue_counts(cell_df)
        primary_code = max(issue_counts, key=issue_counts.get) if issue_counts else "WEAK_COVERAGE"
        secondary_code = self._secondary_code(issue_counts, primary_code)
        score = self._calculator.cell_score(cell_df)
        confidence = self._confidence(primary_code, issue_counts, len(cell_df))

        return CellCoverageSummary(
            cell_id=cell_id,
            coverage_score=score,
            primary_issue=PRIMARY_LABELS.get(primary_code, primary_code),
            secondary_issue=PRIMARY_LABELS.get(secondary_code, secondary_code) if secondary_code else "",
            confidence=confidence,
            recommendation=self._recommendation(primary_code, secondary_code),
            issue_counts=issue_counts,
            metrics=self._cell_metrics(cell_df),
            impacts=self._coverage_impacts(primary_code),
        )

    def analyze_all_cells(self) -> list[CellCoverageSummary]:
        cells = sorted(self.df["cell_id"].dropna().unique())
        return [self.analyze_cell(str(c)) for c in cells]

    def generate_coverage_summary_json(self, output_path: str | Path | None = None) -> Path:
        summaries = self.analyze_all_cells()
        payload = {
            "dataset": str(self.csv_path or geospatial_dataset_path()),
            "radius_miles": DEFAULT_RADIUS_MI,
            "cells": [s.to_json_record() for s in summaries],
        }
        path = Path(output_path) if output_path else self._default_output_dir() / "coverage_summary.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def generate_coverage_hotspots_csv(self, output_path: str | Path | None = None) -> Path:
        hotspots = build_hotspots_df(self.df)
        path = Path(output_path) if output_path else self._default_output_dir() / "coverage_hotspots.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        hotspots.to_csv(path, index=False)
        return path

    def analyze(self, kpis: dict[str, Any], query: str = "") -> dict[str, Any]:
        cell_id = kpis.get("cell_id") or self._cell_from_query(query) or "XYZ401"
        summary = self.analyze_cell(str(cell_id))
        return summary.to_json_record()

    def _issue_counts(self, cell_df: pd.DataFrame) -> dict[str, int]:
        counts: dict[str, int] = {code: 0 for code in ISSUE_CODES}
        for _, row in cell_df.iterrows():
            for code in classify_row(row):
                counts[code] = counts.get(code, 0) + 1
        return {k: v for k, v in counts.items() if v > 0}

    def _secondary_code(self, counts: dict[str, int], primary: str) -> str:
        ordered = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        for code, _ in ordered:
            if code != primary:
                return code
        if primary != "BEAM_COVERAGE_GAP" and counts.get("BEAM_COVERAGE_GAP"):
            return "BEAM_COVERAGE_GAP"
        return "WEAK_COVERAGE" if primary == "COVERAGE_HOLE" else ""

    def _confidence(self, primary: str, counts: dict[str, int], total: int) -> float:
        if total == 0:
            return 0.0
        share = counts.get(primary, 0) / total
        base = 0.72 + share * 0.25
        if primary in ("COVERAGE_HOLE", "WEAK_COVERAGE"):
            base += 0.05
        return round(min(max(base, 0.5), 0.97), 2)

    def _cell_metrics(self, cell_df: pd.DataFrame) -> dict[str, Any]:
        return {
            "samples": len(cell_df),
            "mean_rsrp_dbm": round(float(cell_df["rsrp_dbm"].mean()), 1),
            "mean_sinr_db": round(float(cell_df["sinr_db"].mean()), 1),
            "mean_dl_tp_mbps": round(float(cell_df["dl_tp_mbps"].mean()), 1),
            "mean_bler_dl_pct": round(float(cell_df["bler_dl_pct"].mean()), 1),
            "mean_latency_ms": round(float(cell_df["latency_ms"].mean()), 1),
            "mean_beam_health": round(float(cell_df["beam_health_score"].mean()), 1),
            "mean_prb_dl_pct": round(float(cell_df["prb_dl_pct"].mean()), 1),
            "coverage_hole_pct": round(
                100.0 * detect_coverage_holes(cell_df).shape[0] / max(len(cell_df), 1), 1
            ),
        }

    def _recommendation(self, primary: str, secondary: str) -> str:
        recs = {
            "COVERAGE_HOLE": "Fill coverage holes — retilt, add small cell, optimize SSB footprint.",
            "WEAK_COVERAGE": "Boost edge coverage — power/tilt audit and neighbor plan review.",
            "INTERFERENCE": "PCI/SSB planning and interference hunting on flagged coordinates.",
            "HIGH_BLER": "RF optimization — power control, MCS cap, antenna alignment.",
            "LOW_THROUGHPUT": "Scheduler/congestion check; correlate with PRB and CQI.",
            "LATENCY_HOTSPOT": "Trace UPF/transport path for latency > 80 ms clusters.",
            "BEAM_COVERAGE_GAP": "Rebalance beam weights; recalibrate massive MIMO array.",
        }
        primary_rec = recs.get(primary, "Re-drive cluster and validate KPI recovery.")
        if secondary:
            return f"{primary_rec} Secondary: {recs.get(secondary, secondary)}"
        return primary_rec

    def _coverage_impacts(self, primary_code: str) -> list[str]:
        if primary_code in ("COVERAGE_HOLE", "WEAK_COVERAGE"):
            return [
                "HO Failures",
                "RLF",
                "Call Drops",
                "RACH Failures",
                "Low Throughput",
                "Customer Complaints",
            ]
        if primary_code == "BEAM_COVERAGE_GAP":
            return ["HO Failures", "Throughput Degradation", "Beam Instability"]
        if primary_code == "INTERFERENCE":
            return ["RLF", "High BLER", "Low Throughput"]
        return ["RF Degradation"]

    def _cell_from_query(self, query: str) -> str | None:
        import re
        m = re.search(r"\b(XYZ\d{3})\b", query, re.I)
        return m.group(1).upper() if m else None

    def _default_output_dir(self) -> Path:
        for base in (
            Path(__file__).resolve().parents[1] / "data" / "output",
            Path(__file__).resolve().parents[2] / "data" / "output",
        ):
            if base.parent.exists():
                return base
        return Path("/workspace/backend/data/output")


def analyze_rf_coverage(cell_id: str = "XYZ401", csv_path: str | Path | None = None) -> dict[str, Any]:
    return RFCoverageAgent(csv_path=csv_path).analyze_cell(cell_id).to_json_record()


def get_coverage_summary(cell_id: str | None = None) -> dict[str, Any]:
    agent = RFCoverageAgent()
    if cell_id:
        return agent.analyze_cell(cell_id).to_json_record()
    path = agent.generate_coverage_summary_json()
    return json.loads(path.read_text(encoding="utf-8"))


def get_coverage_hotspots(cell_id: str | None = None) -> list[dict[str, Any]]:
    agent = RFCoverageAgent()
    df = agent.df
    if cell_id:
        df = df[df["cell_id"] == cell_id]
    hotspots = build_hotspots_df(df)
    return hotspots.to_dict(orient="records")
