"""VoNR voice RCA page."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.dashboard_utils import cell_kpis, dataset_cells, default_cell, run_agent, vonr_sessions_df

st.set_page_config(page_title="VoNR", layout="wide")
st.title("📞 VoNR / Voice RCA")
st.caption("5QI-1 session traces, drop causes, IMS/QoS failures · VoNR Agent")

cells = dataset_cells()
cell_id = st.selectbox("Cell", cells, index=cells.index(default_cell()) if default_cell() in cells else 0)

kpis = cell_kpis(cell_id)
df = vonr_sessions_df(cell_id)

c1, c2, c3, c4 = st.columns(4)
c1.metric("VoNR drop rate", f"{kpis.get('vonr_drop_rate', '—')}%")
c2.metric("Setup success", f"{kpis.get('vonr_setup_success_rate', '—')}%")
c3.metric("IMS timeout drops", kpis.get("ims_timeout_count", "—"))
c4.metric("Sessions", kpis.get("vonr_session_count", len(df)))

if not df.empty:
    left, right = st.columns(2)
    with left:
        st.subheader("Result distribution")
        st.bar_chart(df["result"].value_counts())
    with right:
        st.subheader("Drop causes")
        drops = df[df["result"] == "DROP"]
        if not drops.empty:
            st.bar_chart(drops["cause"].value_counts())
    st.subheader("Recent VoNR sessions")
    st.dataframe(df.head(50), use_container_width=True, hide_index=True)

st.subheader("VoNR Agent findings")
agent = run_agent("vonr", cell_id)
st.write(agent["summary"])
if agent["findings"]:
    st.dataframe(pd.DataFrame(agent["findings"]), use_container_width=True)
