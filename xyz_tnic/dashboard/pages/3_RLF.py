"""RLF analytics page."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.dashboard_utils import cell_kpis, dataset_cells, default_cell, rlf_df, run_agent

st.set_page_config(page_title="RLF", layout="wide")
st.title("📶 Radio Link Failure (RLF)")
st.caption("RLF causes, RF conditions, and coverage correlation")

cells = dataset_cells()
cell_id = st.selectbox("Cell", cells, index=cells.index(default_cell()) if default_cell() in cells else 0)

kpis = cell_kpis(cell_id)
df = rlf_df(cell_id)

c1, c2, c3, c4 = st.columns(4)
c1.metric("RLF rate", f"{kpis.get('rlf_rate', '—')}%")
c2.metric("Coverage RLF %", f"{kpis.get('rlf_coverage_pct', '—')}%")
c3.metric("Post-HO RLF %", f"{kpis.get('rlf_post_ho_pct', '—')}%")
c4.metric("Events", len(df))

if not df.empty:
    left, right = st.columns(2)
    with left:
        st.subheader("RLF cause mix")
        st.bar_chart(df["cause"].value_counts())
    with right:
        st.subheader("RSRP distribution")
        st.bar_chart(df["rsrp"].value_counts(bins=8).sort_index())

    st.subheader("RLF event detail")
    st.dataframe(df.head(50), use_container_width=True, hide_index=True)

st.subheader("RLF Agent findings")
agent = run_agent("rlf", cell_id)
st.write(agent["summary"])
if agent["findings"]:
    st.dataframe(pd.DataFrame(agent["findings"]), use_container_width=True)
