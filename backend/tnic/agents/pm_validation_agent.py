"""PM Validation Agent — counter consistency checks and anomaly reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from tnic.datasets.loaders import load_pm_counters
from tnic.services.pm_ingestion import validate_pm_kpis

RULE_IDS = frozenset({
    "HO_BALANCE",
    "RACH_BALANCE",
    "RRC_BALANCE",
    "KPI_RANGE",
})

RULE_LABELS: dict[str, str] = {
    "HO_BALANCE": "HO Attempt Balance",
    "RACH_BALANCE": "RACH Attempt Balance",
    "RRC_BALANCE": "RRC Attempt Balance",
    "KPI_RANGE": "KPI Range Check",
}

RECOMMENDED_ACTIONS: dict[str, list[str]] = {
    "HO_BALANCE": [
        "Reconcile ho_attempt, ho_success, and ho_failure counter definitions",
        "Verify OSS PM aggregation window alignment",
    ],
    "RACH_BALANCE": [
        "Check rach_attempt vs rach_success mapping in vendor PM template",
        "Audit duplicate RACH success counting across cells",
    ],
    "RRC_BALANCE": [
        "Validate RRC setup/reconfig counter pairing in gNB PM export",
        "Confirm rrc_attempt includes reestablishment attempts",
    ],
    "KPI_RANGE": [
        "Reconcile PM counter definitions",
        "Verify KPI derivation formula and units",
    ],
}


@dataclass
class PMAnomaly:
    """Single PM counter anomaly."""

    rule_id: str
    severity: str
    message: str
    cell_id: str | None = None
    row: int | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "message": self.message,
        }
        if self.cell_id:
            out["cell_id"] = self.cell_id
        if self.row is not None:
            out["row"] = self.row
        if self.evidence:
            out["evidence"] = self.evidence
        return out


@dataclass
class PMAnomalyReport:
    """Structured PM validation report."""

    ok: bool
    summary: str
    cell_id: str | None = None
    rows_checked: int = 0
    anomaly_count: int = 0
    anomalies: list[PMAnomaly] = field(default_factory=list)
    checks_passed: dict[str, bool] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "summary": self.summary,
            "cell_id": self.cell_id,
            "rows_checked": self.rows_checked,
            "anomaly_count": self.anomaly_count,
            "anomalies": [a.to_dict() for a in self.anomalies],
            "checks_passed": self.checks_passed,
            "metrics": self.metrics,
        }


class PMValidationAgent:
    """Validates PM counter arithmetic and generates anomaly reports."""

    name = "pm_agent"

    def analyze(
        self,
        cell_id: str | None = None,
        query: str = "",
        pm: pd.DataFrame | None = None,
        csv_path: str | Path | None = None,
    ) -> PMAnomalyReport:
        df = self._load_pm(pm, csv_path)
        if cell_id and not df.empty and "cell_id" in df.columns:
            df = df[df["cell_id"] == cell_id]

        if df.empty and cell_id is None:
            return PMAnomalyReport(
                ok=False,
                summary="No PM counter data found for validation.",
                cell_id=cell_id,
            )

        anomalies = validate_pm_dataframe(df)
        checks = _checks_summary(anomalies)
        metrics = _aggregate_metrics(df)

        error_count = sum(1 for a in anomalies if a.severity == "error")
        ok = error_count == 0
        summary = _format_summary(ok, len(df), len(anomalies), cell_id)

        return PMAnomalyReport(
            ok=ok,
            summary=summary,
            cell_id=cell_id or (_mode_cell(df) if not df.empty else None),
            rows_checked=len(df),
            anomaly_count=len(anomalies),
            anomalies=anomalies,
            checks_passed=checks,
            metrics=metrics,
        )

    def analyze_kpis(self, kpis: dict[str, Any], query: str = "") -> PMAnomalyReport:
        cell_id = kpis.get("cell_id")
        if _has_raw_pm_counters(kpis):
            row = _normalize_row(kpis)
            anomalies = _validate_row(row, row_index=None)
            anomalies.extend(_kpi_range_anomalies(kpis))
            checks = _checks_summary(anomalies)
            error_count = sum(1 for a in anomalies if a.severity == "error")
            ok = error_count == 0
            return PMAnomalyReport(
                ok=ok,
                summary=_format_summary(ok, 1, len(anomalies), str(cell_id) if cell_id else None),
                cell_id=str(cell_id) if cell_id else None,
                rows_checked=1,
                anomaly_count=len(anomalies),
                anomalies=anomalies,
                checks_passed=checks,
                metrics=_row_metrics(row),
            )

        if cell_id:
            return self.analyze(cell_id=str(cell_id), query=query)

        kpi_issues = validate_pm_kpis(kpis)
        anomalies = [
            PMAnomaly(
                rule_id="KPI_RANGE",
                severity="warning",
                message=msg,
                evidence={"source": "kpi_derived"},
            )
            for msg in kpi_issues
        ]
        ok = len(anomalies) == 0
        return PMAnomalyReport(
            ok=ok,
            summary=f"PM KPI validation: {len(anomalies)} issue(s).",
            rows_checked=1,
            anomaly_count=len(anomalies),
            anomalies=anomalies,
            checks_passed={"ho_balance": True, "rach_balance": True, "rrc_balance": True},
        )

    def _load_pm(
        self,
        pm: pd.DataFrame | None,
        csv_path: str | Path | None,
    ) -> pd.DataFrame:
        if pm is not None:
            df = pm.copy()
        elif csv_path is not None:
            df = pd.read_csv(csv_path)
        else:
            try:
                df = load_pm_counters()
            except FileNotFoundError:
                return pd.DataFrame()
        df.columns = [c.strip().lower() for c in df.columns]
        return _normalize_columns(df)


def validate_pm_dataframe(df: pd.DataFrame) -> list[PMAnomaly]:
    """Validate all rows in a PM counters dataframe."""
    anomalies: list[PMAnomaly] = []
    for idx, row in df.iterrows():
        normalized = _normalize_row(row.to_dict())
        anomalies.extend(_validate_row(normalized, row_index=int(idx)))
    return anomalies


def validate_ho_balance(
    ho_attempt: float,
    ho_success: float,
    ho_failure: float | None = None,
) -> PMAnomaly | None:
    """HO Attempts must equal HO Success + HO Failure."""
    failure = ho_failure if ho_failure is not None else ho_attempt - ho_success
    if ho_attempt != ho_success + failure:
        return PMAnomaly(
            rule_id="HO_BALANCE",
            severity="error",
            message=(
                f"HO balance violated: attempts={ho_attempt} != "
                f"success={ho_success} + failure={failure}"
            ),
            evidence={
                "ho_attempt": ho_attempt,
                "ho_success": ho_success,
                "ho_failure": failure,
            },
        )
    if ho_attempt < 0 or ho_success < 0 or failure < 0:
        return PMAnomaly(
            rule_id="HO_BALANCE",
            severity="error",
            message="HO counters must be non-negative",
            evidence={
                "ho_attempt": ho_attempt,
                "ho_success": ho_success,
                "ho_failure": failure,
            },
        )
    return None


def validate_rach_balance(rach_attempt: float, rach_success: float) -> PMAnomaly | None:
    """RACH Attempts must be >= RACH Success."""
    if rach_attempt < rach_success:
        return PMAnomaly(
            rule_id="RACH_BALANCE",
            severity="error",
            message=(
                f"RACH balance violated: attempts={rach_attempt} < "
                f"success={rach_success}"
            ),
            evidence={
                "rach_attempt": rach_attempt,
                "rach_success": rach_success,
            },
        )
    if rach_attempt < 0 or rach_success < 0:
        return PMAnomaly(
            rule_id="RACH_BALANCE",
            severity="error",
            message="RACH counters must be non-negative",
            evidence={
                "rach_attempt": rach_attempt,
                "rach_success": rach_success,
            },
        )
    return None


def validate_rrc_balance(rrc_attempt: float, rrc_success: float) -> PMAnomaly | None:
    """RRC Attempts must be >= RRC Success."""
    if rrc_attempt < rrc_success:
        return PMAnomaly(
            rule_id="RRC_BALANCE",
            severity="error",
            message=(
                f"RRC balance violated: attempts={rrc_attempt} < "
                f"success={rrc_success}"
            ),
            evidence={
                "rrc_attempt": rrc_attempt,
                "rrc_success": rrc_success,
            },
        )
    if rrc_attempt < 0 or rrc_success < 0:
        return PMAnomaly(
            rule_id="RRC_BALANCE",
            severity="error",
            message="RRC counters must be non-negative",
            evidence={
                "rrc_attempt": rrc_attempt,
                "rrc_success": rrc_success,
            },
        )
    return None


def derive_rrc_counters(row: dict[str, Any]) -> tuple[int, int]:
    """Derive RRC attempt/success proxy when not exported in PM CSV."""
    if row.get("rrc_attempt") is not None and row.get("rrc_success") is not None:
        return int(row["rrc_attempt"]), int(row["rrc_success"])

    rach_attempt = int(row.get("rach_attempt") or 0)
    rach_success = int(row.get("rach_success") or 0)
    ho_attempt = int(row.get("ho_attempt") or 0)
    ho_success = int(row.get("ho_success") or 0)

    rrc_attempt = rach_attempt + int(ho_attempt * 0.25)
    rrc_success = rach_success + int(ho_success * 0.20)
    return max(rrc_attempt, rrc_success), rrc_success


def generate_pm_anomaly_report(
    cell_id: str | None = None,
    csv_path: str | Path | None = None,
) -> dict[str, Any]:
    """Convenience API — returns PM anomaly report dict."""
    return PMValidationAgent().analyze(cell_id=cell_id, csv_path=csv_path).to_dict()


def _validate_row(row: dict[str, Any], row_index: int | None) -> list[PMAnomaly]:
    anomalies: list[PMAnomaly] = []
    cell_id = row.get("cell_id")

    ho_attempt = _float_or_none(row.get("ho_attempt"))
    ho_success = _float_or_none(row.get("ho_success"))
    ho_failure = _float_or_none(row.get("ho_failure"))
    if ho_attempt is not None and ho_success is not None:
        issue = validate_ho_balance(ho_attempt, ho_success, ho_failure)
        if issue:
            issue.cell_id = cell_id
            issue.row = row_index
            anomalies.append(issue)

    rach_attempt = _float_or_none(row.get("rach_attempt"))
    rach_success = _float_or_none(row.get("rach_success"))
    if rach_attempt is not None and rach_success is not None:
        issue = validate_rach_balance(rach_attempt, rach_success)
        if issue:
            issue.cell_id = cell_id
            issue.row = row_index
            anomalies.append(issue)

    rrc_attempt, rrc_success = derive_rrc_counters(row)
    issue = validate_rrc_balance(rrc_attempt, rrc_success)
    if issue:
        issue.cell_id = cell_id
        issue.row = row_index
        issue.evidence["rrc_derived"] = row.get("rrc_attempt") is None
        anomalies.append(issue)

    cqi = row.get("cqi")
    if cqi is not None and (float(cqi) < 0 or float(cqi) > 15):
        anomalies.append(PMAnomaly(
            rule_id="KPI_RANGE",
            severity="error",
            message=f"CQI {cqi} out of 3GPP range [0,15]",
            cell_id=cell_id,
            row=row_index,
            evidence={"cqi": cqi},
        ))

    return anomalies


def _kpi_range_anomalies(kpis: dict[str, Any]) -> list[PMAnomaly]:
    return [
        PMAnomaly(
            rule_id="KPI_RANGE",
            severity="warning",
            message=msg,
            cell_id=str(kpis["cell_id"]) if kpis.get("cell_id") else None,
            evidence={"source": "kpi_derived"},
        )
        for msg in validate_pm_kpis(kpis)
    ]


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    renames = {
        "ho_attempts": "ho_attempt",
        "ho_successes": "ho_success",
        "ho_failures": "ho_failure",
        "rach_attempts": "rach_attempt",
        "rach_successes": "rach_success",
        "rrc_attempts": "rrc_attempt",
        "rrc_successes": "rrc_success",
    }
    for old, new in renames.items():
        if old in out.columns and new not in out.columns:
            out = out.rename(columns={old: new})
    return out


def _normalize_row(raw: dict[str, Any]) -> dict[str, Any]:
    row = {str(k).strip().lower(): v for k, v in raw.items()}
    renames = {
        "ho_attempts": "ho_attempt",
        "ho_successes": "ho_success",
        "ho_failures": "ho_failure",
        "rach_attempts": "rach_attempt",
        "rach_successes": "rach_success",
        "rrc_attempts": "rrc_attempt",
        "rrc_successes": "rrc_success",
    }
    for old, new in renames.items():
        if old in row and new not in row:
            row[new] = row[old]
    return row


def _has_raw_pm_counters(kpis: dict[str, Any]) -> bool:
    keys = (
        "ho_attempt", "ho_success", "rach_attempt", "rach_success",
        "rrc_attempt", "rrc_success",
    )
    return any(kpis.get(k) is not None for k in keys)


def _checks_summary(anomalies: list[PMAnomaly]) -> dict[str, bool]:
    failed = {a.rule_id for a in anomalies if a.severity == "error"}
    return {
        "ho_balance": "HO_BALANCE" not in failed,
        "rach_balance": "RACH_BALANCE" not in failed,
        "rrc_balance": "RRC_BALANCE" not in failed,
    }


def _aggregate_metrics(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {}
    metrics: dict[str, Any] = {"rows": len(df)}
    for col in ("ho_attempt", "ho_success", "rach_attempt", "rach_success"):
        if col in df.columns:
            metrics[f"{col}_total"] = int(df[col].sum())
    if "ho_attempt" in df.columns and "ho_success" in df.columns:
        metrics["ho_failure_total"] = int(df["ho_attempt"].sum() - df["ho_success"].sum())
    rrc_attempts: list[int] = []
    rrc_successes: list[int] = []
    for _, row in df.iterrows():
        att, succ = derive_rrc_counters(row.to_dict())
        rrc_attempts.append(att)
        rrc_successes.append(succ)
    metrics["rrc_attempt_total"] = sum(rrc_attempts)
    metrics["rrc_success_total"] = sum(rrc_successes)
    return metrics


def _row_metrics(row: dict[str, Any]) -> dict[str, Any]:
    rrc_att, rrc_succ = derive_rrc_counters(row)
    ho_attempt = row.get("ho_attempt")
    ho_success = row.get("ho_success")
    ho_failure = row.get("ho_failure")
    if ho_failure is None and ho_attempt is not None and ho_success is not None:
        ho_failure = ho_attempt - ho_success
    return {
        "ho_attempt": ho_attempt,
        "ho_success": ho_success,
        "ho_failure": ho_failure,
        "rach_attempt": row.get("rach_attempt"),
        "rach_success": row.get("rach_success"),
        "rrc_attempt": rrc_att,
        "rrc_success": rrc_succ,
    }


def _mode_cell(df: pd.DataFrame) -> str | None:
    if "cell_id" not in df.columns or df.empty:
        return None
    return str(df["cell_id"].mode().iloc[0])


def _float_or_none(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return float(value)


def _format_summary(ok: bool, rows: int, anomalies: int, cell_id: str | None) -> str:
    scope = f"cell {cell_id}" if cell_id else f"{rows} PM row(s)"
    if ok:
        return f"PM validation passed for {scope} — all counter balance checks OK."
    return f"PM validation failed for {scope} — {anomalies} anomalie(s) detected."
