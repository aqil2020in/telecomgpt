"""TelecomGPT Analytics — CSV, log analysis, and interactive charts.

Run:
    pip install -r analytics/requirements.txt
    streamlit run analytics/app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.io as pio
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from analytics.charts import chart_from_csv, level_counts_chart  # noqa: E402
from analytics.csv_tools import csv_summary, load_csv_bytes  # noqa: E402
from analytics.log_tools import log_summary  # noqa: E402

SAMPLES = Path(__file__).resolve().parent / "samples"

st.set_page_config(page_title="TelecomGPT Analytics", layout="wide")
st.title("TelecomGPT Analytics")
st.caption(
    "Upload CSV drive-test data or UE logs — summarize, filter, and chart. "
    "For full file ingest + RCA, open **Upload & Analyze** in the sidebar."
)

tab_csv, tab_log = st.tabs(["CSV data", "Log analysis"])

with tab_csv:
    st.subheader("CSV analysis")
    sample_path = SAMPLES / "drive_test.csv"
    use_sample = st.checkbox("Load sample drive-test CSV", value=False)
    uploaded = st.file_uploader("Upload CSV", type=["csv", "txt"])

    df: pd.DataFrame | None = None
    if use_sample and sample_path.exists():
        df = pd.read_csv(sample_path)
        st.info(f"Using sample: `{sample_path.name}`")
    elif uploaded:
        df = load_csv_bytes(uploaded.read())

    if df is not None:
        summary = csv_summary(df)
        c1, c2, c3 = st.columns(3)
        c1.metric("Rows", summary["rows"])
        c2.metric("Columns", summary["columns"])
        c3.metric("Numeric cols", len(summary["numeric_columns"]))

        st.dataframe(df, use_container_width=True)
        with st.expander("Summary stats"):
            st.json(summary)

        st.subheader("Chart builder")
        cols = summary["column_names"]
        chart_type = st.selectbox(
            "Chart type",
            ["line", "bar", "histogram", "scatter", "box"],
        )
        cc1, cc2, cc3 = st.columns(3)
        x_col = cc1.selectbox("X axis", ["(auto)"] + cols, index=0)
        y_col = cc2.selectbox("Y axis", ["(auto)"] + cols, index=0)
        color_col = cc3.selectbox("Color", ["(none)"] + cols, index=0)

        if st.button("Generate chart", type="primary"):
            fig_json = chart_from_csv(
                df,
                chart_type=chart_type,  # type: ignore[arg-type]
                x=None if x_col == "(auto)" else x_col,
                y=None if y_col == "(auto)" else y_col,
                color=None if color_col == "(none)" else color_col,
            )
            fig = pio.from_json(fig_json)
            st.plotly_chart(fig, use_container_width=True)

with tab_log:
    st.subheader("Log analysis")
    log_sample = SAMPLES / "ue_log.txt"
    use_log_sample = st.checkbox("Load sample UE log", value=False, key="log_sample")
    log_file = st.file_uploader("Upload log file", type=["log", "txt"], key="log_up")

    log_text: str | None = None
    if use_log_sample and log_sample.exists():
        log_text = log_sample.read_text(encoding="utf-8")
        st.info(f"Using sample: `{log_sample.name}`")
    elif log_file:
        log_text = log_file.read().decode("utf-8", errors="replace")

    if log_text:
        summary = log_summary(log_text)
        lc1, lc2, lc3 = st.columns(3)
        lc1.metric("Lines parsed", summary["total_lines"])
        lc2.metric("Errors", summary["error_count"])
        lc3.metric("Lines w/ timestamp", summary["has_timestamps"])

        if summary["level_counts"]:
            fig = level_counts_chart(summary["level_counts"])
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Top error patterns")
        if summary["top_errors"]:
            st.table(summary["top_errors"])
        else:
            st.success("No ERROR/FATAL lines detected.")

        with st.expander("Sample error lines"):
            st.json(summary["sample_errors"])

st.divider()
st.markdown(
    "**API:** same analytics via FastAPI — "
    "`POST /api/analytics/csv/summary`, `/csv/chart`, `/logs/analyze` "
    "(see `/docs` when backend is running)."
)
