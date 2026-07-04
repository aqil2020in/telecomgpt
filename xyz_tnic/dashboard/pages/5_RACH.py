"""RACH analytics page."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.dashboard_utils import cell_kpis, dataset_cells, default_cell, pm_df, rach_df, run_agent

st.set_page_config(page_title="RACH", layout="wide")
st.title("📡 RACH")
st.caption("Random access — MSG1–MSG4 failures and PRACH success")

cells = dataset_cells()
cell_id = st.selectbox("Cell", cells, index=cells.index(default_cell()) if default_cell() in cells else 0)

kpis = cell_kpis(cell_id)
df = rach_df(cell_id)
pm = pm_df(cell_id)

c1, c2, c3, c4 = st.columns(4)
c1.metric("RACH success rate", f"{kpis.get('rach_success_rate', '—')}%")
c2.metric("MSG1 fail %", f"{kpis.get('rach_msg1_fail_rate', '—')}%")
c3.metric("MSG3 fail %", f"{kpis.get('rach_msg3_fail_rate', '—')}%")
c4.metric("Events", len(df))

if not df.empty:
    left, right = st.columns(2)
    with left:
        st.subheader("MSG failure breakdown")
        st.bar_chart(df["msg_failure"].value_counts())
    with right:
        if not pm.empty and "rach_attempt" in pm.columns:
            st.subheader("PM RACH attempts vs success")
            agg = pm.groupby("timestamp", as_index=False)[["rach_attempt", "rach_success"]].sum()
            st.line_chart(agg.set_index("timestamp"))

    st.dataframe(df.head(50), use_container_width=True, hide_index=True)

st.subheader("RACH Agent findings")
agent = run_agent("rach", cell_id)
st.write(agent["summary"])
if agent["findings"]:
    st.dataframe(pd.DataFrame(agent["findings"]), use_container_width=True)
