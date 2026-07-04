"""XYZ TNIC Streamlit dashboard — Operations, Engineering, Executive views."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_URL = os.environ.get("STREAMLIT_API_URL", "http://localhost:8000")
API = f"{API_URL}/api/v1"

st.set_page_config(page_title="XYZ TNIC Dashboard", layout="wide", page_icon="📡")
st.title("📡 XYZ Telecom Network Intelligence Copilot")
st.caption("Operations · Engineering · Executive views")

view = st.sidebar.radio("View", ["Operations", "Engineering RCA", "Executive Summary"])

# Load sample data
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"
pm_df = pd.read_csv(DATA_DIR / "pm_counters_sample.csv") if (DATA_DIR / "pm_counters_sample.csv").exists() else pd.DataFrame()
cell_df = pd.read_csv(DATA_DIR / "cell_kpi_sample.csv") if (DATA_DIR / "cell_kpi_sample.csv").exists() else pd.DataFrame()

if view == "Operations":
    st.header("Operations — Cell KPI Monitor")
    if not cell_df.empty:
        st.dataframe(cell_df, use_container_width=True)
        fig = px.bar(cell_df, x="cell_id", y="throughput_mbps", color="call_drop_rate", title="Throughput vs Drop Rate")
        st.plotly_chart(fig, use_container_width=True)
    st.subheader("PM Counter Sample")
    if not pm_df.empty:
        st.dataframe(pm_df.head(20), use_container_width=True)

elif view == "Engineering RCA":
    st.header("Engineering — RCA Analysis")
    issue = st.selectbox("Issue type", ["handover", "throughput", "call_drop", "rach", "rlf", "latency", "beamforming"])
    query = st.text_input("Query", f"Root cause analysis {issue} on cell 43211")
    cell_id = st.selectbox("Cell", cell_df["cell_id"].tolist() if not cell_df.empty else ["43211"])

    kpis = {}
    if not cell_df.empty:
        row = cell_df[cell_df["cell_id"] == cell_id].iloc[0]
        kpis = row.to_dict()

    col1, col2 = st.columns(2)
    with col1:
        cqi = st.number_input("CQI", value=float(kpis.get("cqi", 7.3)))
        bler = st.number_input("BLER %", value=float(kpis.get("bler", 15.0)))
        sinr = st.number_input("SS-SINR", value=float(kpis.get("ss_sinr", 4.2)))
    with col2:
        ho_rate = st.number_input("HO success %", value=float(kpis.get("ho_success_rate", 91.2)))
        drop_rate = st.number_input("Call drop %", value=float(kpis.get("call_drop_rate", 3.2)))
        tput = st.number_input("Throughput Mbps", value=float(kpis.get("throughput_mbps", 28.5)))

    if st.button("Run RCA", type="primary"):
        payload = {
            "query": query,
            "issue_type": issue,
            "include_rag": True,
            "generate_report": True,
            "kpis": {
                "cell_id": cell_id,
                "cqi": cqi,
                "bler": bler,
                "ss_sinr": sinr,
                "ho_success_rate": ho_rate,
                "call_drop_rate": drop_rate,
                "throughput_mbps": tput,
                "ho_prep_fail_rate": 6.8,
                "beam_failure_ratio": 32.0,
            },
        }
        try:
            r = requests.post(f"{API}/analyze/rca", json=payload, timeout=60)
            if r.ok:
                data = r.json()
                st.success(f"Issue: {data.get('issue_type')} | Health score: {data.get('health_score')}")
                for pc in data.get("probable_root_causes", [])[:3]:
                    st.markdown(f"**{pc['cause']}** — confidence {int(pc['confidence']*100)}%")
                st.markdown("**Actions:**")
                for a in data.get("recommended_actions", [])[:5]:
                    st.markdown(f"- {a}")
                if data.get("narrative_report"):
                    with st.expander("Full RCA Report"):
                        st.markdown(data["narrative_report"])
            else:
                st.error(r.text)
        except Exception as e:
            st.warning(f"API unavailable ({e}). Running offline demo.")
            st.info("Start API: `uvicorn app.main:app --reload` from xyz_tnic/")

else:
    st.header("Executive Summary")
    st.metric("Network cells monitored", len(cell_df) if not cell_df.empty else 3)
    if not cell_df.empty:
        avg_tput = cell_df["throughput_mbps"].mean()
        avg_drop = cell_df["call_drop_rate"].mean()
        st.metric("Avg DL throughput (Mbps)", f"{avg_tput:.1f}")
        st.metric("Avg call drop rate (%)", f"{avg_drop:.1f}")
        health_grades = []
        for _, row in cell_df.iterrows():
            try:
                r = requests.post(f"{API}/health-score/cell", json={
                    "cell_id": row["cell_id"],
                    "kpis": row.to_dict(),
                }, timeout=10)
                if r.ok:
                    health_grades.append(r.json())
            except Exception:
                pass
        if health_grades:
            st.subheader("Cell Health Grades")
            for h in health_grades:
                st.markdown(f"**{h['cell_id']}** — Score {h['overall_score']} ({h['grade']})")

st.sidebar.markdown("---")
st.sidebar.markdown("[API docs](http://localhost:8000/docs)")
