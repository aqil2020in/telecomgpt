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
os.environ.setdefault("TNIC_DATASETS_DIR", str(ROOT / "data" / "datasets"))

from tnic.datasets.kpi_service import build_kpi_input, compute_cell_kpis, list_cell_ids  # noqa: E402
from tnic.models.schemas import AnalyzeRequest  # noqa: E402
from tnic.orchestrator.rca_orchestrator import MasterRCAOrchestrator  # noqa: E402
from tnic.services.incidents import load_incidents  # noqa: E402
from tnic.services.pm_ingestion import ingest_pm_csv  # noqa: E402


def _resolve_api_url(raw: str | None) -> str:
    """Build API base URL from full URL or Render host-only service reference."""
    value = (raw or "http://localhost:8000/api/v1").strip().rstrip("/")
    if value.startswith("http://") or value.startswith("https://"):
        return value if value.endswith("/api/v1") else f"{value}/api/v1"
    return f"https://{value}/api/v1"


API_URL = _resolve_api_url(os.environ.get("TNIC_API_URL"))
DATA = ROOT / "data"
PM_FILE = DATA / "pm_counters.csv"
ORCH = MasterRCAOrchestrator()

DEMO_PRESETS = {
    "Call drop (recommended demo)": "Root cause call drop cell {cell}",
    "Handover failure": "handover failure cell {cell}",
    "RACH MSG3 failure": "RACH MSG3 failure cell {cell}",
    "RLF": "RLF radio link failure cell {cell}",
    "Throughput (preview — agent may be silent)": "low throughput cell {cell}",
    "Beamforming (preview — agent may be silent)": "beam failure cell {cell}",
    "Latency (preview — agent may be silent)": "latency spike cell {cell}",
}

DEMO_READY = {"Call drop (recommended demo)", "Handover failure", "RACH MSG3 failure", "RLF"}


def _dataset_cells() -> list[str]:
    cells = list_cell_ids()
    return cells if cells else ["XYZ401"]


def _health_for_cell(cell: str) -> dict:
    from tnic.services.health_scoring import compute_health_score

    bundle = compute_cell_kpis(cell)
    health = compute_health_score(bundle.kpis)
    health["overall_score"] = bundle.health_score or health["overall_score"]
    return {"bundle": bundle, "health": health}


st.set_page_config(page_title="XYZ TNIC Dashboard", layout="wide")
st.title("XYZ Telecom Network Intelligence Copilot")
st.caption(
    "Demo-ready: call drop · handover · RACH · RLF on dataset cells XYZ401–XYZ410. "
    "Throughput / beam / latency agents need KPI pipeline (roadmap)."
)

cells = _dataset_cells()
default_cell = "XYZ401" if "XYZ401" in cells else cells[0]

tab_rca, tab_health, tab_pm, tab_incidents, tab_api = st.tabs(
    ["RCA Analysis", "Cell Health", "PM Counters", "Incidents", "API Status"]
)

with tab_rca:
    st.subheader("Root Cause Analysis")
    col_cell, col_preset = st.columns(2)
    with col_cell:
        cell_id = st.selectbox("Cell (telecom datasets)", cells, index=cells.index(default_cell))
    with col_preset:
        preset = st.selectbox("Demo preset", list(DEMO_PRESETS.keys()), index=0)
    if preset not in DEMO_READY:
        st.info("This preset is preview-only until throughput/beam/latency KPIs are wired.")

    query = st.text_input("Query", value=DEMO_PRESETS[preset].format(cell=cell_id))
    generate_report = st.checkbox("Generate OpenAI narrative report", value=False)

    if st.button("Run RCA", type="primary"):
        kpi_input = build_kpi_input(cell_id=cell_id, query=query)
        req = AnalyzeRequest(
            query=query,
            kpis=kpi_input,
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
                st.write(f"- [{pc.get('category', '?')}] {pc['cause']} ({int(pc['confidence'] * 100)}%)")
        if result.findings:
            st.write("**Findings**")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "rule_id": f.rule_id,
                            "category": f.category,
                            "confidence": round(f.confidence, 2),
                            "cause": f.probable_cause[:120],
                        }
                        for f in result.findings[:15]
                    ]
                ),
                use_container_width=True,
            )
        if result.recommended_actions:
            st.write("**Recommended actions**")
            for a in result.recommended_actions[:8]:
                st.write(f"- {a}")
        if result.rag_context:
            with st.expander("Knowledge base context"):
                for hit in result.rag_context[:3]:
                    st.markdown(f"**{hit.get('title', 'Playbook')}** ({hit.get('category', '')})")
                    st.caption((hit.get("text") or "")[:300])
        if result.narrative_report:
            st.markdown(result.narrative_report)
        with st.expander("Full JSON response"):
            st.json(json.loads(result.model_dump_json()))

with tab_health:
    st.subheader("Cell Health Score")
    cell = st.selectbox("Cell", cells, key="health_cell", index=cells.index(default_cell))
    data = _health_for_cell(cell)
    bundle = data["bundle"]
    score = data["health"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Overall score", f"{score['overall_score']}/100")
    c2.metric("Grade", score["grade"])
    c3.metric("Alerts", len(score["alerts"]))
    st.bar_chart(pd.Series(score["dimensions"]))
    st.caption(f"KPI sources: {', '.join(bundle.sources) or 'none'}")
    if score["alerts"]:
        for a in score["alerts"]:
            st.warning(a)


with tab_pm:
    st.subheader("PM Counter Ingestion")
    if PM_FILE.exists():
        st.write(f"Legacy sample PM: `{PM_FILE.name}` (dashboard RCA uses `/datasets` cells above)")
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
    st.subheader("API Health & demo endpoints")
    st.code(
        "\n".join(
            [
                f"GET  {API_URL}/health",
                f"GET  {API_URL}/cell/{default_cell}",
                f"POST {API_URL}/analyze-ho",
                f"POST {API_URL}/generate-rca",
                f"POST {API_URL}/analyze-cell",
            ]
        )
    )
    if st.button("Check API"):
        try:
            r = requests.get(f"{API_URL}/health", timeout=5)
            st.json(r.json())
        except Exception as e:
            st.error(f"API unreachable: {e}")
            st.info("Start API with: uvicorn tnic.main:app --host 0.0.0.0 --port 8000")
