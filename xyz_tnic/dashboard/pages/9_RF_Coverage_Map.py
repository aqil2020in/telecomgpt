"""RF Coverage — Google Maps 3-mile drive-test page."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from tnic.agents.rf_coverage_agent import RFCoverageAgent  # noqa: E402
from tnic.services.coverage_google_map import render_google_maps_html  # noqa: E402
from tnic.services.coverage_optimizer import DEFAULT_RADIUS_MI, geospatial_dataset_path  # noqa: E402

st.set_page_config(page_title="RF Coverage Map", layout="wide")
st.title("🗺️ RF Coverage — Google Maps Drive Test")
st.caption("3-mile site radius · enhanced geospatial RF dataset · best/weak zone ranking")

radius = st.slider("Radius (miles)", 1.0, 5.0, DEFAULT_RADIUS_MI, 0.5)
query = st.text_input(
    "Query",
    value=f"RF coverage optimizer {radius} mile radius drive test Dallas SITE01",
)

if st.button("Run RF Coverage Agent", type="primary"):
    with st.spinner("Analyzing drive-test trace..."):
        diagnosis = RFCoverageAgent().analyze_drive_test(query=query, radius_miles=radius)

    if diagnosis.issue_class == "No Data":
        st.error(diagnosis.root_cause)
    else:
        st.success(diagnosis.summary)
        c1, c2, c3, c4 = st.columns(4)
        m = diagnosis.metrics
        c1.metric("Issue class", diagnosis.issue_class)
        c2.metric("Confidence", f"{int(diagnosis.confidence * 100)}%")
        c3.metric("Samples in radius", m.get("points_in_radius", "—"))
        c4.metric("Weak zones", m.get("weak_zone_count", "—"))

        st.info(diagnosis.root_cause)
        st.subheader("Evidence")
        for item in diagnosis.evidence:
            st.write(f"- {item}")
        st.subheader("Recommendations")
        for i, rec in enumerate(diagnosis.recommendations, 1):
            st.write(f"{i}. {rec}")

        if diagnosis.map_artifact and diagnosis.map_artifact.get("map_data"):
            st.subheader("Google Maps — drive route")
            st.caption(
                "Gray route = drive path · Green = best UE locations · Red = weak zones · "
                "Orange = coverage holes · Blue = suggested verify · Purple = site · Indigo circle = radius"
            )
            html = render_google_maps_html(diagnosis.map_artifact["map_data"])
            components.html(html, height=580, scrolling=False)

            opt = diagnosis.optimization
            left, right = st.columns(2)
            with left:
                st.subheader("Top measured locations")
                if opt.get("best_measured"):
                    st.dataframe(pd.DataFrame(opt["best_measured"]), use_container_width=True)
            with right:
                st.subheader("Coverage status mix")
                mix = opt.get("coverage_status_mix") or {}
                if mix:
                    st.bar_chart(pd.Series(mix))

try:
    st.caption(f"Dataset: `{geospatial_dataset_path()}`")
except FileNotFoundError as exc:
    st.warning(str(exc))
