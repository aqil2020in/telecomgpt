"""5G RACH Failure Agent — analyzes rach_events.csv for access RCA."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from tnic.datasets.loaders import load_rach_events

MSG_FAILURE_CODES = frozenset({"MSG1", "MSG2", "MSG3", "MSG4"})

MSG_LABELS: dict[str, str] = {
    "MSG1": "MSG1 Failure",
    "MSG2": "MSG2 Failure",
    "MSG3": "MSG3 Failure",
    "MSG4": "MSG4 Failure",
}

ROOT_CAUSE_CODES = frozenset({"COVERAGE", "INTERFERENCE", "PRACH_MISCONFIG", "BEAM_ISSUE"})

ROOT_CAUSE_LABELS: dict[str, str] = {
    "COVERAGE": "Coverage",
    "INTERFERENCE": "Interference",
    "PRACH_MISCONFIG": "PRACH Misconfig",
    "BEAM_ISSUE": "Beam Issue",
}

ROOT_CAUSE_DETAIL: dict[str, str] = {
    "COVERAGE": (
        "Weak PRACH/payload RF at cell edge — preamble or Msg3 not decoded; "
        "RSRP below access threshold."
    ),
    "INTERFERENCE": (
        "Co-channel or adjacent-sector interference on PRACH/PUSCH — "
        "preamble or Msg3 corrupted despite moderate RSRP."
    ),
    "PRACH_MISCONFIG": (
        "PRACH parameter mismatch — root sequence, occasion, or "
        "prach-ConfigurationIndex collision with neighbor/DAS."
    ),
    "BEAM_ISSUE": (
        "SSB/beam selection mismatch — UE accessed on suboptimal beam; "
        "RAR or Msg4 not received on active beam."
    ),
}

BASE_CONFIDENCE: dict[str, float] = {
    "MSG1": 0.80,
    "MSG2": 0.78,
    "MSG3": 0.82,
    "MSG4": 0.74,
}

ROOT_CAUSE_CONFIDENCE: dict[str, float] = {
    "COVERAGE": 0.84,
    "INTERFERENCE": 0.79,
    "PRACH_MISCONFIG": 0.81,
    "BEAM_ISSUE": 0.74,
}

MSG_QUERY_HINTS: dict[str, str] = {
    "msg1": "MSG1",
    "msg 1": "MSG1",
    "preamble": "MSG1",
    "msg2": "MSG2",
    "msg 2": "MSG2",
    "rar": "MSG2",
    "msg3": "MSG3",
    "msg 3": "MSG3",
    "msg4": "MSG4",
    "msg 4": "MSG4",
}

ROOT_QUERY_HINTS: dict[str, str] = {
    "coverage": "COVERAGE",
    "cell edge": "COVERAGE",
    "interference": "INTERFERENCE",
    "co-channel": "INTERFERENCE",
    "prach misconfig": "PRACH_MISCONFIG",
    "prach config": "PRACH_MISCONFIG",
    "root sequence": "PRACH_MISCONFIG",
    "beam issue": "BEAM_ISSUE",
    "beam failure": "BEAM_ISSUE",
    "ssb beam": "BEAM_ISSUE",
}


@dataclass(frozen=True)
class RACHDiagnosis:
    """Structured RACH failure diagnosis."""

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


class RACHFailureAgent:
    """Telecom-grade RACH failure analyzer over rach_events.csv."""

    name = "rach_agent"

    def analyze(
        self,
        cell_id: str | None = None,
        query: str = "",
        events: pd.DataFrame | None = None,
        csv_path: str | Path | None = None,
    ) -> RACHDiagnosis:
        df = self._load_events(events, csv_path)
        if cell_id and not df.empty and "cell_id" in df.columns:
            df = df[df["cell_id"] == cell_id]
        if df.empty:
            return RACHDiagnosis(
                failure_type="No Data",
                root_cause="No RACH events found for the requested scope.",
                confidence=0.0,
                cell_id=cell_id,
            )

        enriched = _enrich_events(df)
        failures = enriched[enriched["msg_code"].isin(MSG_FAILURE_CODES)]
        if failures.empty:
            return RACHDiagnosis(
                failure_type="No Failure",
                root_cause="All RACH attempts succeeded — no Msg1–Msg4 failure signature detected.",
                confidence=0.55,
                cell_id=cell_id or str(df["cell_id"].mode().iloc[0]),
                evidence={"rach_success_pct": round(100.0 * (df["msg_failure"] == "SUCCESS").mean(), 2)},
            )

        msg_counts = failures["msg_code"].value_counts()
        root_counts = failures["root_cause_code"].value_counts()

        msg_hint = _msg_from_query(query)
        root_hint = _root_from_query(query)

        msg_code = msg_hint if msg_hint else str(msg_counts.index[0])
        msg_subset = failures[failures["msg_code"] == msg_code]
        if msg_subset.empty and msg_hint:
            msg_subset = failures.head(3)

        root_counts_for_msg = (
            msg_subset["root_cause_code"].value_counts()
            if not msg_subset.empty
            else root_counts
        )
        root_code = root_hint if root_hint else str(root_counts_for_msg.index[0])
        root_subset = failures[failures["root_cause_code"] == root_code]
        if root_subset.empty and root_hint:
            root_subset = failures.head(3)

        confidence = _score_confidence(msg_code, root_code, msg_counts, root_counts, len(failures))
        root_text = _format_root_cause(
            root_code, msg_code,
            msg_subset if not msg_subset.empty else failures.head(3),
        )
        evidence = _build_evidence(
            failures,
            msg_subset if not msg_subset.empty else failures,
            msg_code,
            root_code,
        )

        return RACHDiagnosis(
            failure_type=MSG_LABELS.get(msg_code, msg_code),
            root_cause=root_text,
            confidence=confidence,
            cell_id=cell_id or str(failures["cell_id"].mode().iloc[0]),
            evidence=evidence,
        )

    def analyze_kpis(self, kpis: dict[str, Any], query: str = "") -> RACHDiagnosis:
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
            df = load_rach_events()
        df.columns = [c.strip().lower() for c in df.columns]
        if "msg_failure" not in df.columns and "msg_failure" not in df.columns:
            pass
        return df


def classify_root_cause(
    msg_code: str,
    rsrp: float | None = None,
    sinr: float | None = None,
) -> str:
    """Map RACH Msg failure stage + RF to root cause category."""
    if msg_code == "MSG1":
        if rsrp is not None and rsrp <= -110:
            return "COVERAGE"
        if sinr is not None and sinr <= 0:
            return "INTERFERENCE"
        return "PRACH_MISCONFIG"
    if msg_code == "MSG2":
        if sinr is not None and sinr <= 0:
            return "INTERFERENCE"
        return "PRACH_MISCONFIG"
    if msg_code == "MSG3":
        if rsrp is not None and rsrp <= -108:
            return "COVERAGE"
        if sinr is not None and sinr <= 0:
            return "INTERFERENCE"
        return "PRACH_MISCONFIG"
    if msg_code == "MSG4":
        if rsrp is not None and rsrp > -95 and (sinr is None or sinr > 8):
            return "BEAM_ISSUE"
        if sinr is not None and sinr <= 0:
            return "INTERFERENCE"
        return "BEAM_ISSUE"
    return "PRACH_MISCONFIG"


def _normalize_msg(raw: str | None) -> str | None:
    if raw is None or pd.isna(raw):
        return None
    key = str(raw).strip().upper()
    if key == "SUCCESS":
        return None
    if key in MSG_FAILURE_CODES:
        return key
    return None


def _enrich_events(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    msg_codes: list[str | None] = []
    root_codes: list[str] = []

    for row in out.itertuples(index=False):
        msg_raw = getattr(row, "msg_failure", None)
        msg = _normalize_msg(msg_raw)
        rsrp = getattr(row, "rsrp", None) if hasattr(row, "rsrp") else None
        sinr = getattr(row, "sinr", None) if hasattr(row, "sinr") else None
        rsrp_f = float(rsrp) if rsrp is not None and pd.notna(rsrp) else None
        sinr_f = float(sinr) if sinr is not None and pd.notna(sinr) else None

        msg_codes.append(msg)
        if msg:
            root_codes.append(classify_root_cause(msg, rsrp_f, sinr_f))
        else:
            root_codes.append("")

    out["msg_code"] = msg_codes
    out["root_cause_code"] = root_codes
    return out


def _msg_from_query(query: str) -> str | None:
    ql = query.lower()
    for hint, code in sorted(MSG_QUERY_HINTS.items(), key=lambda x: len(x[0]), reverse=True):
        if hint in ql:
            return code
    return None


def _root_from_query(query: str) -> str | None:
    ql = query.lower()
    for hint, code in sorted(ROOT_QUERY_HINTS.items(), key=lambda x: len(x[0]), reverse=True):
        if hint in ql:
            return code
    return None


def _build_evidence(
    failures: pd.DataFrame,
    msg_subset: pd.DataFrame,
    msg_code: str,
    root_code: str,
) -> dict[str, Any]:
    return {
        "msg_code": msg_code,
        "failure_type": MSG_LABELS.get(msg_code, msg_code),
        "root_cause_code": root_code,
        "root_cause_category": ROOT_CAUSE_LABELS.get(root_code, root_code),
        "failure_count": int(len(msg_subset)),
        "total_failures": int(len(failures)),
        "msg_distribution": failures["msg_code"].value_counts().to_dict(),
        "root_cause_distribution": {
            ROOT_CAUSE_LABELS.get(k, k): int(v)
            for k, v in failures["root_cause_code"].value_counts().items()
            if k
        },
    }


def _score_confidence(
    msg_code: str,
    root_code: str,
    msg_counts: pd.Series,
    root_counts: pd.Series,
    total_failures: int,
) -> float:
    msg_dom = int(msg_counts.get(msg_code, 0)) / total_failures if total_failures else 0.0
    root_dom = int(root_counts.get(root_code, 0)) / total_failures if total_failures else 0.0
    base = (BASE_CONFIDENCE.get(msg_code, 0.75) + ROOT_CAUSE_CONFIDENCE.get(root_code, 0.75)) / 2
    score = base * 0.55 + msg_dom * 0.25 + root_dom * 0.20
    return round(min(max(score, 0.40), 0.95), 2)


def _format_root_cause(root_code: str, msg_code: str, subset: pd.DataFrame) -> str:
    label = ROOT_CAUSE_LABELS.get(root_code, root_code)
    detail = ROOT_CAUSE_DETAIL.get(root_code, "RACH failure detected.")
    msg_label = MSG_LABELS.get(msg_code, msg_code)
    extra = f" Dominant stage: {msg_label}."
    if not subset.empty and "rsrp" in subset.columns:
        rsrp = subset["rsrp"].dropna()
        if len(rsrp):
            extra += f" Mean RSRP: {float(rsrp.mean()):.1f} dBm."
    if not subset.empty and "sinr" in subset.columns:
        sinr = subset["sinr"].dropna()
        if len(sinr):
            extra += f" Mean SINR: {float(sinr.mean()):.1f} dB."
    return f"{label}: {detail}{extra}"


def diagnose_rach(
    cell_id: str | None = None,
    query: str = "",
    csv_path: str | Path | None = None,
) -> dict[str, Any]:
    """Convenience API — returns {failure_type, root_cause, confidence}."""
    return RACHFailureAgent().analyze(cell_id=cell_id, query=query, csv_path=csv_path).to_dict()
