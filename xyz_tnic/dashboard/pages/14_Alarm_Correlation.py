"""FM alarm correlation RCA page."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.dashboard_utils import alarm_df, cell_kpis, dataset_cells, default_cell, run_agent

st.set_page_config(page_title="Alarm Correlation", layout="wide")
st.title("🚨 FM Alarm Correlation")
st.caption("Critical/major alarms correlated with KPI degradation · Alarm Agent")

cells = dataset_cells()
cell_id = st.selectbox("Cell", cells, index=cells.index(default_cell()) if default_cell() in cells else 0)

kpis = cell_kpis(cell_id)
df = alarm_df(cell_id)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Active alarms", kpis.get("active_alarm_count", len(df)))
c2.metric("Critical", kpis.get("critical_alarm_count", "—"))
c3.metric("Transport alarms", kpis.get("transport_alarm_count", "—"))
c4.metric("HW alarms", kpis.get("hw_alarm_count", "—"))

if not df.empty:
    left, right = st.columns(2)
    with left:
        st.subheader("Alarm names")
        st.bar_chart(df["alarm_name"].value_counts())
    with right:
        st.subheader("Severity")
        st.bar_chart(df["severity"].value_counts())
    st.subheader("Alarm timeline")
    st.dataframe(df.head(50), use_container_width=True, hide_index=True)

st.subheader("Alarm Correlation Agent findings")
agent = run_agent("alarm", cell_id)
st.write(agent["summary"])
if agent["findings"]:
    st.dataframe(pd.DataFrame(agent["findings"]), use_container_width=True)
