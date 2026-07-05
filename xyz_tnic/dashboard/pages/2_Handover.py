"""Handover analytics page."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.dashboard_utils import cell_kpis, dataset_cells, default_cell, handover_df, run_agent

st.set_page_config(page_title="Handover", layout="wide")
st.title("🔄 Handover")
st.caption("HO attempts, success rate, failure mix, and mobility RCA")

cells = dataset_cells()
cell_id = st.selectbox("Cell", cells, index=cells.index(default_cell()) if default_cell() in cells else 0)

kpis = cell_kpis(cell_id)
df = handover_df(cell_id)

c1, c2, c3, c4 = st.columns(4)
c1.metric("HO success rate", f"{kpis.get('ho_success_rate', '—')}%")
c2.metric("Prep fail rate", f"{kpis.get('ho_prep_fail_rate', '—')}%")
c3.metric("Xn fail rate", f"{kpis.get('ho_xn_fail_rate', '—')}%")
c4.metric("Events", len(df))

if not df.empty:
    left, right = st.columns(2)
    with left:
        st.subheader("Failure type distribution")
        counts = df["failure_type"].value_counts()
        st.bar_chart(counts)
    with right:
        st.subheader("RSRP / SINR at HO")
        rsrp_col = "serving_rsrp" if "serving_rsrp" in df.columns else "rsrp"
        sinr_col = "serving_sinr" if "serving_sinr" in df.columns else "sinr"
        st.scatter_chart(df[[rsrp_col, sinr_col]])

    if "failure_stage" in df.columns:
        st.subheader("Failure stage mix")
        st.bar_chart(df["failure_stage"].value_counts())

    st.subheader("Recent handover events")
    show_cols = [
        c for c in (
            "timestamp", "ue_id", "source_cell", "target_cell", "failure_type",
            "failure_stage", "serving_rsrp", "target_rsrp", "rca_scenarios", "result",
        )
        if c in df.columns
    ]
    st.dataframe(df[show_cols].head(50) if show_cols else df.head(50), use_container_width=True, hide_index=True)

st.subheader("HO Agent findings")
agent = run_agent("handover", cell_id)
st.write(agent["summary"])
if agent["findings"]:
    st.dataframe(pd.DataFrame(agent["findings"]), use_container_width=True)
