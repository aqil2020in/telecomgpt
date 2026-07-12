"""RCA Report page."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.dashboard_utils import dataset_cells, default_cell, run_rca, run_rca_from_upload

st.set_page_config(page_title="RCA Report", layout="wide")
st.title("🔍 RCA Report")
st.caption("Master orchestrator — multi-agent root cause analysis and narrative report")

data_source = st.radio(
    "Data source",
    ["Preloaded datasets", "Upload telecom_issues.csv"],
    horizontal=True,
    help="Upload a unified CSV with issue_domain column (handover, rlf, vonr, …) for upload-driven RCA.",
)

uploaded_file = None
upload_bytes = None
if data_source == "Upload telecom_issues.csv":
    st.info(
        "Upload **telecom_issues.csv** — one file with columns: "
        "`timestamp, cell_id, ue_id, issue_domain, event_type, result, cause, rsrp, sinr, …`"
    )
    uploaded_file = st.file_uploader(
        "telecom_issues.csv",
        type=["csv", "xlsx", "xls"],
        help="Generate from repo: python scripts/generate_telecom_issues.py",
    )
    if uploaded_file is not None:
        upload_bytes = uploaded_file.getvalue()

cells = dataset_cells()
cell_id = st.selectbox("Cell", cells, index=cells.index(default_cell()) if default_cell() in cells else 0)

PRESETS = {
    "Auto-detect from upload": "telecom RCA auto detect cell {cell}",
    "Call drop": "Root cause call drop cell {cell}",
    "Handover failure": "handover failure cell {cell}",
    "RLF coverage hole": "RLF coverage hole cell {cell}",
    "RACH MSG3 failure": "RACH MSG3 failure cell {cell}",
    "Throughput degradation": "low throughput cell {cell}",
    "Beam failure": "beam failure cell {cell}",
    "VoNR drop": "VoNR voice drop IMS failure cell {cell}",
    "ANR / PCI conflict": "ANR PCI conflict missing neighbor cell {cell}",
    "Config drift": "configuration drift CM audit cell {cell}",
    "Syslog correlation": "gNB syslog NGAP XnAP HO failure cell {cell}",
    "Alarm correlation": "FM alarm transport packet loss cell {cell}",
    "Unified coverage RCA": "coverage hole RLF handover call drop cell {cell}",
}
preset = st.selectbox("Demo preset", list(PRESETS.keys()))
query = st.text_input("Query", value=PRESETS[preset].format(cell=cell_id))
generate_report = st.checkbox("Generate structured narrative report", value=False)

if st.button("Run Master RCA", type="primary"):
    if data_source == "Upload telecom_issues.csv" and not upload_bytes:
        st.error("Upload telecom_issues.csv first.")
        st.stop()

    with st.spinner("Running specialist agents..."):
        if data_source == "Upload telecom_issues.csv" and upload_bytes:
            payload = run_rca_from_upload(
                uploaded_file.name,
                upload_bytes,
                cell_id=cell_id,
                query=query,
                generate_report=generate_report,
            )
            key_issues = payload.get("key_issues") or []
            rca_raw = payload.get("rca") or {}
            from tnic.models.schemas import RCAResponse

            result = RCAResponse.model_validate(rca_raw) if rca_raw.get("issue_type") else None
            if result is None and isinstance(rca_raw, dict) and rca_raw.get("findings"):
                result = RCAResponse.model_validate(rca_raw)
        else:
            result = run_rca(cell_id, query, generate_report=generate_report)
            key_issues = []

    if key_issues:
        st.subheader("Key issues detected (from upload)")
        st.dataframe(
            pd.DataFrame([
                {
                    "domain": i.get("domain"),
                    "issue": i.get("title"),
                    "summary": i.get("summary"),
                    "severity": i.get("severity"),
                }
                for i in key_issues
            ]),
            use_container_width=True,
        )

    if result is None:
        st.error("RCA did not return results. Check upload format (issue_domain + event_type columns).")
        st.stop()

    st.success(f"Issue domain: **{result.issue_type}** · Health: **{result.health_score}/100**")
    st.write("**Agents:**", " → ".join(result.agents_run))

    if result.narrative_structured:
        n = result.narrative_structured
        st.subheader("Executive Summary")
        st.write(n.executive_summary)
        st.subheader("Root Cause")
        st.info(n.root_cause)
        st.subheader("Evidence")
        for item in n.evidence:
            st.write(f"- {item}")
        st.subheader("Recommendations")
        for i, rec in enumerate(n.recommendations, 1):
            st.write(f"{i}. {rec}")
        st.metric("Confidence", f"{int(n.confidence * 100)}%")
    elif result.narrative_report:
        st.markdown(result.narrative_report)

    if result.probable_root_causes:
        st.subheader("Probable root causes")
        st.dataframe(pd.DataFrame(result.probable_root_causes), use_container_width=True)

    if result.findings:
        st.subheader("All findings")
        st.dataframe(
            pd.DataFrame([
                {
                    "category": f.category,
                    "confidence": round(f.confidence, 2),
                    "cause": f.probable_cause[:100],
                    "rule_id": f.rule_id,
                }
                for f in result.findings[:20]
            ]),
            use_container_width=True,
        )

    if result.recommended_actions:
        st.subheader("Recommended actions")
        for action in result.recommended_actions[:8]:
            st.write(f"- {action}")

    with st.expander("Full JSON"):
        st.json(json.loads(result.model_dump_json()))
