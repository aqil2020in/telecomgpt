"""Assurance datasets hub — all upgraded RCA agents."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.dashboard_utils import ALL_AGENTS, dataset_cells, default_cell, run_all_agents

st.set_page_config(page_title="Assurance Hub", layout="wide")
st.title("🛡️ Assurance Hub — Upgraded RCA Agents")
st.caption("VoNR · ANR · Config Audit · gNB Syslog · Alarm · cross-domain evidence")

cells = dataset_cells()
cell_id = st.selectbox("Cell", cells, index=cells.index(default_cell()) if default_cell() in cells else 0)

if st.button("Run all 12 specialist agents", type="primary"):
    with st.spinner("Running agents..."):
        results = run_all_agents(cell_id)
    rows = []
    for r in results:
        top = r["findings"][0]["probable_cause"][:80] if r["findings"] else "—"
        conf = r["findings"][0].get("confidence", 0) if r["findings"] else 0
        rows.append({
            "agent": r["agent"],
            "findings": len(r["findings"]),
            "top_confidence": round(conf, 2),
            "summary": r["summary"][:100],
            "top_cause": top,
        })
    st.subheader("Agent readiness matrix")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.subheader("Registered agents")
st.table({name: label for name, label in ALL_AGENTS})

st.info(
    "Assurance datasets: gnb_syslog.csv · cell_configuration.csv · "
    "neighbor_relations.csv · anr_events.csv · vonr_sessions.csv · alarm_events.csv · "
    "ue_protocol_trace.csv"
)
