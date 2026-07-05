"""gNB syslog correlation RCA page."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.dashboard_utils import cell_kpis, dataset_cells, default_cell, gnb_syslog_df, run_agent

st.set_page_config(page_title="gNB Syslog", layout="wide")
st.title("📋 gNB Syslog Correlation")
st.caption("DU/CU log signatures — HO, RLF, RACH, VoNR, Transport · gNB Syslog Agent")

cells = dataset_cells()
cell_id = st.selectbox("Cell", cells, index=cells.index(default_cell()) if default_cell() in cells else 0)

kpis = cell_kpis(cell_id)
df = gnb_syslog_df(cell_id)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Log events", kpis.get("syslog_event_count", len(df)))
c2.metric("HO prep fail logs", kpis.get("syslog_ho_prep_fail_count", "—"))
c3.metric("RLF T310 logs", kpis.get("syslog_t310_count", "—"))
c4.metric("Signatures matched", len(kpis.get("syslog_signatures", []) or []))

if not df.empty:
    left, right = st.columns(2)
    with left:
        st.subheader("Event codes")
        st.bar_chart(df["event_code"].value_counts())
    with right:
        st.subheader("Modules")
        st.bar_chart(df["module"].value_counts())
    st.subheader("Recent syslog entries")
    st.dataframe(df.head(50), use_container_width=True, hide_index=True)

st.subheader("gNB Syslog Agent findings")
agent = run_agent("gnb_syslog", cell_id)
st.write(agent["summary"])
if agent["findings"]:
    st.dataframe(pd.DataFrame(agent["findings"]), use_container_width=True)
