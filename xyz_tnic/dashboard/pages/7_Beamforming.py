"""Beamforming analytics page."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.dashboard_utils import (
    cell_kpis,
    dataset_cells,
    default_cell,
    run_agent,
    synthesize_beam_metrics,
)

st.set_page_config(page_title="Beamforming", layout="wide")
st.title("🎯 Beamforming")
st.caption("SSB beam utilization, switches, and massive MIMO KPIs (synthesized from RF datasets)")

cells = dataset_cells()
cell_id = st.selectbox("Cell", cells, index=cells.index(default_cell()) if default_cell() in cells else 0)

kpis = cell_kpis(cell_id)
beams = synthesize_beam_metrics(cell_id)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Beam fail ratio", f"{kpis.get('beam_failure_ratio', '—')}%")
c2.metric("Peak beam util", f"{beams['beam_utilization'].max():.1f}%")
c3.metric("Peak beam index", int(beams.loc[beams["beam_utilization"].idxmax(), "beam_index"]))
c4.metric("SSB beams", len(beams))

left, right = st.columns(2)
with left:
    st.subheader("Beam utilization by index")
    st.bar_chart(beams.set_index("beam_index")["beam_utilization"])
with right:
    st.subheader("Beam switches by index")
    st.bar_chart(beams.set_index("beam_index")["beam_switches"])

st.subheader("Per-beam RF profile")
st.dataframe(beams, use_container_width=True, hide_index=True)

st.subheader("Beamforming Agent findings")
agent = run_agent("beamforming", cell_id)
st.write(agent["summary"])
if agent["findings"]:
    st.dataframe(pd.DataFrame(agent["findings"]), use_container_width=True)
