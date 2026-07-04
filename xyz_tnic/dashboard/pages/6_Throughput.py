"""Throughput analytics page."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.dashboard_utils import cell_kpis, dataset_cells, default_cell, run_agent, throughput_df

st.set_page_config(page_title="Throughput", layout="wide")
st.title("⚡ Throughput")
st.caption("DL throughput, CQI, PRB utilization, and scheduler issues")

cells = dataset_cells()
cell_id = st.selectbox("Cell", cells, index=cells.index(default_cell()) if default_cell() in cells else 0)

kpis = cell_kpis(cell_id)
df = throughput_df(cell_id)

c1, c2, c3, c4 = st.columns(4)
c1.metric("DL throughput", f"{kpis.get('throughput_mbps', '—')} Mbps")
c2.metric("Mean CQI", kpis.get("cqi", "—"))
c3.metric("PRB util", f"{kpis.get('prb_utilization', '—')}%")
c4.metric("Top issue", kpis.get("throughput_top_issue", "—"))

if not df.empty:
    left, right = st.columns(2)
    with left:
        st.subheader("Throughput vs CQI")
        st.scatter_chart(df[["dl_tp", "cqi"]])
    with right:
        st.subheader("Issue tags")
        labeled = df[df["issue"].notna() & (df["issue"] != "None")]
        if not labeled.empty:
            st.bar_chart(labeled["issue"].value_counts())
        else:
            st.info("No labeled throughput issues in sample.")

    st.subheader("Throughput metrics")
    st.dataframe(df.head(50), use_container_width=True, hide_index=True)

st.subheader("Throughput Agent findings")
agent = run_agent("throughput", cell_id)
st.write(agent["summary"])
if agent["findings"]:
    st.dataframe(pd.DataFrame(agent["findings"]), use_container_width=True)
