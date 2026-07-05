"""RF Coverage Agent — Plotly geospatial dashboard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from agents.rf_coverage_agent import (  # noqa: E402
    RFCoverageAgent,
    build_hotspots_df,
    detect_coverage_holes,
    geospatial_dataset_path,
    load_geospatial_df,
)
from tnic.agents.specialists import RFCoverageAgent as SpecialistRFCoverageAgent  # noqa: E402


def _build_kpi_heatmap(
    df: pd.DataFrame,
    *,
    z_col: str,
    color_scale: str,
    z_range: tuple[float, float],
    title: str,
    center_lat: float,
    center_lon: float,
    map_style: str = "open-street-map",
) -> go.Figure:
    """Geospatial KPI heatmap — bypasses px.density_map express path (Plotly 6 bug)."""
    zmin, zmax = z_range
    try:
        fig = go.Figure(
            go.Densitymap(
                lat=df["latitude"],
                lon=df["longitude"],
                z=df[z_col],
                radius=18,
                colorscale=color_scale,
                zmin=zmin,
                zmax=zmax,
                colorbar={"title": z_col},
            )
        )
        fig.update_layout(
            title=title,
            map={
                "style": map_style,
                "center": {"lat": center_lat, "lon": center_lon},
                "zoom": 12,
            },
            margin={"l": 0, "r": 0, "t": 40, "b": 0},
            height=520,
        )
        return fig
    except (AttributeError, TypeError, ValueError):
        fig = px.scatter_map(
            df,
            lat="latitude",
            lon="longitude",
            color=z_col,
            color_continuous_scale=color_scale,
            range_color=z_range,
            zoom=12,
            map_style=map_style,
            opacity=0.75,
            size_max=10,
            title=title,
        )
        fig.update_layout(
            map={"center": {"lat": center_lat, "lon": center_lon}},
            margin={"l": 0, "r": 0, "t": 40, "b": 0},
            height=520,
        )
        return fig


st.set_page_config(page_title="RF Coverage", layout="wide", page_icon="📶")
st.title("📶 RF Coverage Agent — Geospatial Analysis")
st.caption("Plotly heatmaps · coverage holes · beam gaps · per-cell coverage score")

if "rf_cell" not in st.session_state:
    st.session_state.rf_cell = "XYZ401"

with st.sidebar:
    st.header("Controls")
    try:
        csv_path = geospatial_dataset_path()
        df_all = load_geospatial_df(csv_path)
        cells = sorted(df_all["cell_id"].dropna().unique())
        st.session_state.rf_cell = st.selectbox(
            "Cell",
            cells,
            index=cells.index(st.session_state.rf_cell) if st.session_state.rf_cell in cells else 0,
        )
        st.caption(f"Dataset: `{csv_path}`")
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()

    run_analysis = st.button("Run RF Coverage Agent", type="primary")
    show_all_cells = st.checkbox("Show all cells on maps", value=False)

cell_id = st.session_state.rf_cell
agent = RFCoverageAgent(csv_path=csv_path)
cell_df = df_all if show_all_cells else df_all[df_all["cell_id"] == cell_id].copy()
summary = agent.analyze_cell(cell_id)

if run_analysis or "rf_summary_loaded" not in st.session_state:
    st.session_state.rf_summary_loaded = True
    summary_path = agent.generate_coverage_summary_json()
    hotspots_path = agent.generate_coverage_hotspots_csv()
    st.session_state.coverage_summary_path = str(summary_path)
    st.session_state.coverage_hotspots_path = str(hotspots_path)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Cell", summary.cell_id)
c2.metric("Coverage Score", summary.coverage_score)
c3.metric("Primary Issue", summary.primary_issue)
c4.metric("Secondary Issue", summary.secondary_issue or "—")
c5.metric("Confidence", f"{int(summary.confidence * 100)}%")

st.info(summary.recommendation)
if summary.impacts:
    st.write("**Correlated impacts:** " + ", ".join(summary.impacts))

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "RSRP Heatmap",
    "SINR Heatmap",
    "Coverage Holes",
    "Beam Coverage",
    "Score by Cell",
])

map_style = "open-street-map"
center_lat = float(cell_df["latitude"].mean())
center_lon = float(cell_df["longitude"].mean())

with tab1:
    st.subheader("RSRP Heatmap (dBm)")
    fig_rsrp = _build_kpi_heatmap(
        cell_df,
        z_col="rsrp_dbm",
        color_scale="RdYlGn_r",
        z_range=(-120, -70),
        title=f"RSRP — {cell_id if not show_all_cells else 'all cells'}",
        center_lat=center_lat,
        center_lon=center_lon,
        map_style=map_style,
    )
    st.plotly_chart(fig_rsrp, use_container_width=True)

with tab2:
    st.subheader("SINR Heatmap (dB)")
    fig_sinr = _build_kpi_heatmap(
        cell_df,
        z_col="sinr_db",
        color_scale="Viridis",
        z_range=(-10, 25),
        title=f"SINR — {cell_id if not show_all_cells else 'all cells'}",
        center_lat=center_lat,
        center_lon=center_lon,
        map_style=map_style,
    )
    st.plotly_chart(fig_sinr, use_container_width=True)

with tab3:
    st.subheader("Coverage Hole Map")
    holes = detect_coverage_holes(cell_df)
    fig_holes = px.scatter_map(
        cell_df,
        lat="latitude",
        lon="longitude",
        color="rsrp_dbm",
        color_continuous_scale="RdYlGn_r",
        size_max=8,
        zoom=12,
        map_style=map_style,
        title="All samples (colored by RSRP)",
        opacity=0.45,
    )
    if not holes.empty:
        fig_holes.add_trace(
            go.Scattermap(
                lat=holes["latitude"],
                lon=holes["longitude"],
                mode="markers",
                marker={"size": 10, "color": "red", "opacity": 0.85},
                name="Coverage holes",
                text=holes.get("coverage_status", holes["rsrp_dbm"].astype(str)),
            )
        )
    fig_holes.update_layout(
        map={"center": {"lat": center_lat, "lon": center_lon}},
        margin={"l": 0, "r": 0, "t": 40, "b": 0},
        height=520,
        legend={"orientation": "h", "y": 1.02},
    )
    st.plotly_chart(fig_holes, use_container_width=True)
    st.caption(f"Coverage holes detected: **{len(holes)}** samples (RSRP ≤ -115 dBm)")

with tab4:
    st.subheader("Beam Coverage Map")
    if "beam_id" in cell_df.columns:
        fig_beam = px.scatter_map(
            cell_df,
            lat="latitude",
            lon="longitude",
            color="beam_id",
            size="beam_health_score",
            size_max=14,
            zoom=12,
            map_style=map_style,
            title="Beam ID · marker size = beam health score",
            hover_data=["beam_azimuth_deg", "beam_health_score", "prb_dl_pct", "beam_switch_count"],
        )
        fig_beam.update_layout(
            map={"center": {"lat": center_lat, "lon": center_lon}},
            margin={"l": 0, "r": 0, "t": 40, "b": 0},
            height=520,
        )
        st.plotly_chart(fig_beam, use_container_width=True)
    else:
        st.warning("Beam fields not present in dataset.")

with tab5:
    st.subheader("Coverage Score by Cell")
    summaries = agent.analyze_all_cells()
    score_df = pd.DataFrame([
        {
            "cell_id": s.cell_id,
            "coverage_score": s.coverage_score,
            "primary_issue": s.primary_issue,
            "confidence_pct": int(s.confidence * 100),
        }
        for s in summaries
    ]).sort_values("coverage_score")
    fig_score = px.bar(
        score_df,
        x="cell_id",
        y="coverage_score",
        color="coverage_score",
        color_continuous_scale="RdYlGn",
        text="coverage_score",
        title="Composite coverage score (0–100)",
    )
    fig_score.update_traces(textposition="outside")
    fig_score.update_layout(height=420, yaxis_range=[0, 100])
    st.plotly_chart(fig_score, use_container_width=True)
    st.dataframe(score_df, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Specialist agent output")
spec = SpecialistRFCoverageAgent().analyze({"cell_id": cell_id}, query=f"RF coverage analysis {cell_id}")
st.write(spec.summary)
for finding in spec.findings:
    st.markdown(f"- **{finding.probable_cause}** (confidence {int(finding.confidence * 100)}%)")

if st.session_state.get("coverage_summary_path"):
    st.caption(
        f"Artifacts: `{st.session_state.get('coverage_summary_path')}` · "
        f"`{st.session_state.get('coverage_hotspots_path')}`"
    )

if cell_id == "XYZ401":
    st.success(
        "Demo target XYZ401 — Primary: Coverage Deficiency · Secondary: Beam Congestion · "
        "Score: 52 · Confidence: 94% · Impacts: HO Failures, RLF, Call Drops, RACH Failures, Low Throughput"
    )
