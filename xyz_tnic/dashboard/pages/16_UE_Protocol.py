"""UE Protocol Correlation Agent dashboard page."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.dashboard_utils import cell_kpis, dataset_cells, default_cell, run_agent, ue_trace_df

st.set_page_config(page_title="UE Protocol", layout="wide")
st.title("📱 UE Protocol Correlation")
st.caption("PHY · RACH · RRC · NAS · Mobility · RLF · 5GSM · IMS — UE-side trace RCA")

cells = dataset_cells()
cell_id = st.selectbox("Cell", cells, index=cells.index(default_cell()) if default_cell() in cells else 0)

df = ue_trace_df(cell_id)
fail_df = df[df["result"].astype(str).str.upper().isin(("FAIL", "FAILURE", "DROP", "REJECT", "TIMEOUT"))]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Trace rows", len(df))
c2.metric("Failure events", len(fail_df))
c3.metric("Affected UEs", fail_df["ue_id"].nunique() if not fail_df.empty else 0)
c4.metric("Layers", fail_df["layer"].nunique() if not fail_df.empty else 0)

if not fail_df.empty:
    left, right = st.columns(2)
    with left:
        st.subheader("Failures by layer")
        st.bar_chart(fail_df["layer"].value_counts())
    with right:
        st.subheader("Failures by procedure")
        st.bar_chart(fail_df["procedure"].value_counts())
    st.subheader("UE protocol trace (failures)")
    st.dataframe(fail_df, use_container_width=True, hide_index=True)

st.subheader("UE Protocol Agent findings")
agent = run_agent("ue_protocol", cell_id)
st.write(agent["summary"])
if agent["findings"]:
    st.dataframe(pd.DataFrame(agent["findings"]), use_container_width=True)
