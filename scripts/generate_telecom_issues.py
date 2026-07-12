#!/usr/bin/env python3
"""Build datasets/telecom_issues.csv from existing per-domain CSV files."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "xyz_tnic"))

from tnic.datasets.registry import datasets_dir  # noqa: E402
from tnic.datasets.telecom_issues import UNIFIED_COLUMNS  # noqa: E402


def _row(**kwargs) -> dict:
    base = {c: "" for c in UNIFIED_COLUMNS}
    base.update(kwargs)
    return base


def _result_from_failure(failure_type: str) -> str:
    return "SUCCESS" if str(failure_type).upper() == "SUCCESS" else "FAIL"


def from_handover(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        ft = str(r.get("failure_type", "EVENT"))
        rows.append(_row(
            cell_id=r.get("cell_id", ""),
            ue_id=r.get("ue_id", ""),
            issue_domain="handover",
            event_type=ft,
            result=_result_from_failure(ft),
            rsrp=r.get("rsrp", ""),
            sinr=r.get("sinr", ""),
            source_cell=r.get("cell_id", ""),
        ))
    return rows


def from_rlf(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        cause = r.get("cause", "")
        rows.append(_row(
            cell_id=r.get("cell_id", ""),
            ue_id=r.get("ue_id", ""),
            issue_domain="rlf",
            event_type="RLF",
            result="FAIL" if str(cause).strip() and str(cause) != "None" else "SUCCESS",
            cause=cause,
            rsrp=r.get("rsrp", ""),
            sinr=r.get("sinr", ""),
        ))
    return rows


def from_rach(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        msg = str(r.get("msg_failure", "MSG1"))
        rows.append(_row(
            cell_id=r.get("cell_id", ""),
            ue_id=r.get("ue_id", ""),
            issue_domain="rach",
            event_type=msg,
            result="SUCCESS" if msg.upper() == "SUCCESS" else "FAIL",
        ))
    return rows


def from_call_drop(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        dt = str(r.get("drop_type", "Unknown"))
        rows.append(_row(
            cell_id=r.get("cell_id", ""),
            ue_id=r.get("ue_id", ""),
            issue_domain="call_drop",
            event_type=dt,
            result="FAIL",
            cause=dt,
        ))
    return rows


def from_throughput(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        issue = str(r.get("issue", "None"))
        rows.append(_row(
            cell_id=r.get("cell_id", ""),
            issue_domain="throughput",
            event_type=issue,
            result="FAIL" if issue not in ("None", "", "nan") else "SUCCESS",
            cqi=r.get("cqi", ""),
            prb_util=r.get("prb_util", ""),
            dl_tp=r.get("dl_tp", ""),
        ))
    return rows


def from_vonr(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        result = str(r.get("result", "SUCCESS"))
        rows.append(_row(
            timestamp=r.get("timestamp", ""),
            cell_id=r.get("cell_id", ""),
            ue_id=r.get("ue_id", ""),
            issue_domain="vonr",
            event_type=r.get("event", "VONR"),
            result=result,
            cause=r.get("cause", ""),
        ))
    return rows


def from_anr(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        et = str(r.get("event_type", "ANR"))
        rows.append(_row(
            timestamp=r.get("timestamp", ""),
            cell_id=r.get("cell_id", ""),
            issue_domain="anr",
            event_type=et,
            result="FAIL" if "FAIL" in et.upper() or "CONFLICT" in et.upper() or "MISSING" in et.upper() else "SUCCESS",
            details=r.get("details", ""),
        ))
    return rows


def from_alarm(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        sev = str(r.get("severity", ""))
        rows.append(_row(
            timestamp=r.get("timestamp", ""),
            cell_id=r.get("cell_id", ""),
            issue_domain="alarm",
            event_type=r.get("alarm_name", "ALARM"),
            result="FAIL" if sev.upper() in ("CRITICAL", "MAJOR") else "WARN",
            severity=sev,
            alarm_name=r.get("alarm_name", ""),
        ))
    return rows


def from_syslog(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        code = str(r.get("event_code", "SYSLOG"))
        sev = str(r.get("severity", ""))
        rows.append(_row(
            timestamp=r.get("timestamp", ""),
            cell_id=r.get("cell_id", ""),
            ue_id=r.get("ue_id", ""),
            issue_domain="gnb_syslog",
            event_type=code,
            result="FAIL" if sev.upper() in ("CRITICAL", "MAJOR", "ERROR", "WARN") else "SUCCESS",
            severity=sev,
            module=r.get("module", ""),
            event_code=code,
            message=r.get("message", ""),
        ))
    return rows


def from_beamforming(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        score = float(r.get("beam_health_score", 100) or 100)
        switch_rate = float(r.get("beam_switch_rate_per_min", 0) or 0)
        ho = str(r.get("ho_status", ""))
        et = "BEAM_FAILURE" if score < 70 or switch_rate > 4 else "BEAM_OK"
        if ho and "FAIL" in ho.upper():
            et = "BEAM_HO_CORRELATED"
        rows.append(_row(
            timestamp=r.get("timestamp", ""),
            cell_id=r.get("cell_id", ""),
            ue_id=r.get("ue_id", ""),
            issue_domain="beamforming",
            event_type=et,
            result="FAIL" if et != "BEAM_OK" else "SUCCESS",
            rsrp=r.get("rsrp_dbm", r.get("rsrp", "")),
            sinr=r.get("sinr_db", r.get("sinr", "")),
            cqi=r.get("cqi", ""),
            dl_tp=r.get("dl_tp_mbps", ""),
            beam_id=r.get("beam_id", ""),
            beam_health_score=score,
            beam_switch_rate=switch_rate,
            details=f"ho_status={ho}",
        ))
    return rows


def from_ue_protocol(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        result = str(r.get("result", "SUCCESS"))
        rows.append(_row(
            timestamp=r.get("timestamp", ""),
            cell_id=r.get("cell_id", ""),
            ue_id=r.get("ue_id", ""),
            issue_domain="ue_protocol",
            event_type=str(r.get("message", r.get("procedure", "UE_EVENT"))),
            result=result,
            cause=r.get("cause", ""),
            details=f"layer={r.get('layer','')} procedure={r.get('procedure','')}",
        ))
    return rows


def from_pm(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        ho_rate = (float(r.get("ho_success", 0)) / max(float(r.get("ho_attempt", 1)), 1))
        rows.append(_row(
            timestamp=r.get("timestamp", ""),
            cell_id=r.get("cell_id", ""),
            issue_domain="pm",
            event_type="PM_SNAPSHOT",
            result="SUCCESS" if ho_rate >= 0.95 else "FAIL",
            cqi=r.get("cqi", ""),
            dl_tp=r.get("dl_tp", ""),
            details=f"ho_attempt={r.get('ho_attempt','')} rach_attempt={r.get('rach_attempt','')}",
        ))
    return rows


def main() -> None:
    ddir = datasets_dir()
    out = ddir / "telecom_issues.csv"
    all_rows: list[dict] = []

    loaders = [
        ("handover_events.csv", from_handover),
        ("rlf_events.csv", from_rlf),
        ("rach_events.csv", from_rach),
        ("call_drop_events.csv", from_call_drop),
        ("throughput_metrics.csv", from_throughput),
        ("vonr_sessions.csv", from_vonr),
        ("anr_events.csv", from_anr),
        ("alarm_events.csv", from_alarm),
        ("gnb_syslog.csv", from_syslog),
        ("enhanced_geospatial_rf_dataset.csv", from_beamforming),
        ("ue_protocol_trace.csv", from_ue_protocol),
        ("pm_counters.csv", from_pm),
    ]

    for fname, fn in loaders:
        path = ddir / fname
        if not path.exists():
            print(f"skip missing {fname}")
            continue
        df = pd.read_csv(path)
        df.columns = [c.strip().lower() for c in df.columns]
        rows = fn(df)
        all_rows.extend(rows)
        print(f"{fname}: {len(rows)} rows")

    out_df = pd.DataFrame(all_rows, columns=list(UNIFIED_COLUMNS))
    out_df.to_csv(out, index=False)
    print(f"\nWrote {len(out_df)} rows -> {out}")


if __name__ == "__main__":
    main()
