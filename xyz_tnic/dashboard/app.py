"""XYZ Telecom Network Intelligence Copilot — Streamlit dashboard."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("APP_ENV", "development")

from tnic.models.schemas import AnalyzeRequest, KPIInput  # noqa: E402
from tnic.orchestrator.rca_orchestrator import MasterRCAOrchestrator  # noqa: E402
from tnic.services.health_scoring import compute_health_score  # noqa: E402
from tnic.services.incidents import load_incidents  # noqa: E402
from tnic.services.pm_ingestion import aggregate_cell_kpis, ingest_pm_csv  # noqa: E402

API_URL = os.environ.get("TNIC_API_URL", "http://localhost:8000/api/v1")
DATA = ROOT / "data"
PM_FILE = DATA / "pm_counters.csv"
ORCH = MasterRCAOrchestrator()

st.set_page_config(page_title="XYZ TNIC Dashboard", layout="wide")
st.title("XYZ Telecom Network Intelligence Copilot")
st.caption("Multi-agent 5G RCA · PM validation · Health scoring · Incident library")

tab_rca, tab_health, tab_pm, tab_incidents, tab_api = st.tabs(
    ["RCA Analysis", "Cell Health", "PM Counters", "Incidents", "API Status"]
)

with tab_rca:
    st.subheader("Root Cause Analysis")
    query = st.text_input("Query", value="Root cause analysis call drop on cell 43211")
    col1, col2 = st.columns(2)
    with col1:
        cell_id = st.selectbox("Cell (from PM data)", ["43211", "43212"])
    with col2:
        generate_report = st.checkbox("Generate OpenAI narrative report", value=False)

    if st.button("Run RCA", type="primary"):
        kpis: dict = {}
        if PM_FILE.exists():
            agg = aggregate_cell_kpis(PM_FILE)
            kpis = agg.get(cell_id, {})
        req = AnalyzeRequest(
            query=query,
            kpis=KPIInput(**{k: v for k, v in kpis.items() if k in KPIInput.model_fields}),
            include_rag=True,
            generate_report=generate_report,
        )
        with st.spinner("Running specialist agents..."):
            result = ORCH.run(req)
        st.success(f"Issue: **{result.issue_type}** · Health: **{result.health_score}/100**")
        st.write("**Agents run:**", " → ".join(result.agents_run))
        if result.probable_root_causes:
            st.write("**Probable root causes**")
            for pc in result.probable_root_causes[:5]:
                st.write(f"- {pc['cause']} ({int(pc['confidence']*100)}%)")
        if result.recommended_actions:
            st.write("**Recommended actions**")
            for a in result.recommended_actions[:8]:
                st.write(f"- {a}")
        if result.narrative_report:
            st.markdown(result.narrative_report)
        with st.expander("Full JSON response"):
            st.json(json.loads(result.model_dump_json()))

with tab_health:
    st.subheader("Cell Health Score")
    if not PM_FILE.exists():
        st.error(f"PM file not found: {PM_FILE}")
    else:
        agg = aggregate_cell_kpis(PM_FILE)
        cell = st.selectbox("Cell", list(agg.keys()), key="health_cell")
        kpis = agg[cell]
        score = compute_health_score(kpis)
        c1, c2, c3 = st.columns(3)
        c1.metric("Overall score", f"{score['overall_score']}/100")
        c2.metric("Grade", score["grade"])
        c3.metric("Alerts", len(score["alerts"]))
        st.bar_chart(pd.Series(score["dimensions"]))
        if score["alerts"]:
            for a in score["alerts"]:
                st.warning(a)

with tab_pm:
    st.subheader("PM Counter Ingestion")
    if PM_FILE.exists():
        st.write(f"Sample dataset: `{PM_FILE.name}`")
        df = pd.read_csv(PM_FILE)
        st.dataframe(df, use_container_width=True)
        if st.button("Ingest sample PM CSV to database"):
            result = ingest_pm_csv(PM_FILE)
            st.success(f"Ingested {result['rows_ingested']} rows across {len(result['cells'])} cells")
            if result["validation_issues"]:
                for issue in result["validation_issues"]:
                    st.warning(issue)
    uploaded = st.file_uploader("Upload PM CSV", type=["csv"])
    if uploaded is not None:
        tmp = DATA / "_upload_pm.csv"
        tmp.write_bytes(uploaded.read())
        result = ingest_pm_csv(tmp)
        st.json(result)
        tmp.unlink(missing_ok=True)

with tab_incidents:
    st.subheader("Telecom Incident Library")
    try:
        incidents = load_incidents()
        df = pd.DataFrame(incidents)
        st.dataframe(df, use_container_width=True)
        issue_filter = st.selectbox("Filter by issue type", ["all"] + sorted({i["issue_type"] for i in incidents}))
        if issue_filter != "all":
            st.dataframe(df[df["issue_type"] == issue_filter], use_container_width=True)
    except Exception as e:
        st.error(str(e))

with tab_api:
    st.subheader("API Health")
    st.code(f"GET {API_URL}/health")
    if st.button("Check API"):
        try:
            r = requests.get(f"{API_URL}/health", timeout=5)
            st.json(r.json())
        except Exception as e:
            st.error(f"API unreachable: {e}")
            st.info("Start API with: uvicorn tnic.main:app --host 0.0.0.0 --port 8000")
