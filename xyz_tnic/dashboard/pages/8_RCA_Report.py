"""RCA Report page."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.dashboard_utils import dataset_cells, default_cell, run_rca

st.set_page_config(page_title="RCA Report", layout="wide")
st.title("🔍 RCA Report")
st.caption("Master orchestrator — multi-agent root cause analysis and narrative report")

cells = dataset_cells()
cell_id = st.selectbox("Cell", cells, index=cells.index(default_cell()) if default_cell() in cells else 0)

PRESETS = {
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
generate_report = st.checkbox("Generate structured narrative report", value=True)

if st.button("Run Master RCA", type="primary"):
    with st.spinner("Running specialist agents..."):
        result = run_rca(cell_id, query, generate_report=generate_report)

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
