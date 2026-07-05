"""Configuration audit RCA page."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.dashboard_utils import cell_config_df, cell_kpis, dataset_cells, default_cell, run_agent

st.set_page_config(page_title="Config Audit", layout="wide")
st.title("⚙️ Configuration Audit")
st.caption("CM golden baseline validation · A3, TTT, hysteresis, PCI, neighbors")

cells = dataset_cells()
cell_id = st.selectbox("Cell", cells, index=cells.index(default_cell()) if default_cell() in cells else 0)

kpis = cell_kpis(cell_id)
cfg = cell_config_df(cell_id)

c1, c2, c3, c4 = st.columns(4)
c1.metric("A3 offset (dB)", kpis.get("ho_a3_offset_db", "—"))
c2.metric("TTT (ms)", kpis.get("ho_time_to_trigger_ms", "—"))
c3.metric("Hysteresis (dB)", kpis.get("ho_hysteresis_db", "—"))
c4.metric("Config drift count", kpis.get("config_drift_count", 0))

if not cfg.empty:
    st.subheader("Live cell configuration (CM export)")
    st.dataframe(cfg, use_container_width=True, hide_index=True)

st.subheader("Config Audit Agent findings")
agent = run_agent("config_audit", cell_id)
st.write(agent["summary"])
if agent["findings"]:
    st.dataframe(pd.DataFrame(agent["findings"]), use_container_width=True)
