"""Call drop analytics page."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.dashboard_utils import call_drop_df, cell_kpis, dataset_cells, default_cell, run_agent

st.set_page_config(page_title="Call Drops", layout="wide")
st.title("📵 Call Drops")
st.caption("Drop classification — Radio, Mobility, IMS, Core, Transport")

cells = dataset_cells()
cell_id = st.selectbox("Cell", cells, index=cells.index(default_cell()) if default_cell() in cells else 0)

kpis = cell_kpis(cell_id)
df = call_drop_df(cell_id)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Call drop rate", f"{kpis.get('call_drop_rate', '—')}%")
c2.metric("Dominant type", kpis.get("dominant_drop_type", "—"))
c3.metric("Mobility drops", f"{kpis.get('drop_mobility_pct', '—')}%")
c4.metric("Events", len(df))

if not df.empty:
    st.subheader("Drop type distribution")
    st.bar_chart(df["drop_type"].value_counts())
    st.dataframe(df.head(50), use_container_width=True, hide_index=True)

st.subheader("Call Drop Agent findings")
agent = run_agent("call_drop", cell_id)
st.write(agent["summary"])
if agent["findings"]:
    st.dataframe(pd.DataFrame(agent["findings"]), use_container_width=True)
