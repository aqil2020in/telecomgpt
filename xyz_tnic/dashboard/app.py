"""XYZ Telecom Dashboard — Executive Summary (home)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.dashboard_utils import (  # noqa: E402
    cell_health,
    dataset_cells,
    default_cell,
    executive_summary_df,
    worst_cells,
)
from dashboard.rca_workflow_section import render_rca_workflow_section  # noqa: E402

st.set_page_config(
    page_title="XYZ Telecom TNIC",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📡 XYZ Telecom Network Intelligence")
st.caption("Executive Summary · Demo cells XYZ401–XYZ410 · Dummy telecom datasets")

cells = dataset_cells()
if "selected_cell" not in st.session_state:
    st.session_state.selected_cell = default_cell()

with st.sidebar:
    st.header("Navigation")
    st.info(
        "Pages: Handover · RLF · Call Drops · RACH · Throughput · Beamforming · "
        "VoNR · ANR · Config Audit · gNB Syslog · Alarm · Assurance Hub · Upload · RCA Report"
    )
    st.session_state.selected_cell = st.selectbox(
        "Focus cell",
        cells,
        index=cells.index(st.session_state.selected_cell)
        if st.session_state.selected_cell in cells
        else 0,
    )

summary = executive_summary_df()
worst = worst_cells(5)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Cells monitored", len(summary))
c2.metric("Cluster avg health", f"{summary['health_score'].mean():.1f}/100")
c3.metric("Worst cell", worst[0] if worst else "—")
c4.metric("Cells grade D/C", int((summary["grade"].isin(["C", "D"])).sum()))

render_rca_workflow_section()
st.divider()

st.subheader("Network health overview")
st.dataframe(
    summary.sort_values("health_score"),
    use_container_width=True,
    hide_index=True,
)

left, right = st.columns(2)
with left:
    st.subheader("Health score by cell")
    chart_df = summary.set_index("cell_id")[["health_score"]].sort_values("health_score")
    st.bar_chart(chart_df, color="#2563eb")
with right:
    st.subheader("Mobility & reliability")
    mob = summary.set_index("cell_id")[["ho_success_rate", "rlf_rate", "call_drop_rate"]]
    st.line_chart(mob)

st.subheader("RF & throughput snapshot")
rf = summary.set_index("cell_id")[["ss_rsrp", "ss_sinr", "throughput_mbps", "rach_success_rate"]]
st.dataframe(rf, use_container_width=True)

focus = st.session_state.selected_cell
health = cell_health(focus)
st.divider()
st.subheader(f"Focus cell — {focus}")
m1, m2, m3 = st.columns(3)
m1.metric("Health score", f"{health['overall_score']}/100")
m2.metric("Grade", health["grade"])
m3.metric("Alerts", len(health["alerts"]))
st.bar_chart(pd.Series(health["dimensions"]), horizontal=True)
if health["alerts"]:
    for alert in health["alerts"]:
        st.warning(alert)

st.caption("Data: PM/HO/RLF/RACH + assurance datasets (syslog, CM, ANR, VoNR, alarms)")
