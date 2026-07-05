"""ANR / neighbor relation RCA page."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.dashboard_utils import (
    anr_events_df,
    cell_kpis,
    dataset_cells,
    default_cell,
    neighbor_relations_df,
    run_agent,
)

st.set_page_config(page_title="ANR", layout="wide")
st.title("🔗 ANR / Neighbor Relations")
st.caption("PCI conflict, missing neighbor, stale NCR · ANR + Mobility Agents")

cells = dataset_cells()
cell_id = st.selectbox("Cell", cells, index=cells.index(default_cell()) if default_cell() in cells else 0)

kpis = cell_kpis(cell_id)
anr_df = anr_events_df(cell_id)
nbr_df = neighbor_relations_df(cell_id)

c1, c2, c3, c4 = st.columns(4)
c1.metric("PCI conflicts", kpis.get("pci_conflict_count", kpis.get("anr_pci_conflict_count", "—")))
c2.metric("Missing neighbors", kpis.get("missing_neighbor_count", kpis.get("anr_missing_neighbor_count", "—")))
c3.metric("NR neighbor count", kpis.get("nr_neighbor_count", "—"))
c4.metric("ANR events", kpis.get("anr_event_count", len(anr_df)))

if not anr_df.empty:
    st.subheader("ANR event types")
    st.bar_chart(anr_df["event_type"].value_counts())

if not nbr_df.empty:
    st.subheader("Neighbor relations")
    st.dataframe(nbr_df, use_container_width=True, hide_index=True)

st.subheader("ANR Agent findings")
agent = run_agent("anr", cell_id)
st.write(agent["summary"])
if agent["findings"]:
    st.dataframe(pd.DataFrame(agent["findings"]), use_container_width=True)
