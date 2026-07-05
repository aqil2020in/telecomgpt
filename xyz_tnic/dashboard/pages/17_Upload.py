"""Dynamic upload and ingestion dashboard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.dashboard_utils import (
    dataset_cells,
    ingest_upload_bytes,
    list_upload_history,
    run_upload_rca,
)

st.set_page_config(page_title="Upload & Ingest", layout="wide")
st.title("📤 Upload & Dynamic Ingestion")
st.caption(
    "Drag-and-drop CSV · XLSX · JSON · TXT · LOG · PCAP · ZIP — "
    "auto classify → normalize → RCA"
)

API_BASE = st.sidebar.text_input("API base URL", value="http://127.0.0.1:8000/api/v1")

workflow = st.radio(
    "RCA workflow",
    [
        "New Upload RCA",
        "Historical RCA",
        "Single Cell RCA",
        "Single UE RCA",
        "Multi-Cell RCA",
    ],
    horizontal=True,
)

uploaded = st.file_uploader(
    "Upload telecom file",
    type=["csv", "xlsx", "xls", "json", "txt", "log", "pcap", "zip"],
    accept_multiple_files=False,
)

cells = [""] + dataset_cells()
cell_id = st.selectbox("Cell ID (optional)", cells, index=0)
ue_id = st.text_input("UE ID (optional)", value="")
query = st.text_input("RCA query (optional)", value="")
run_rca = st.checkbox("Run RCA automatically after upload", value=True)

if uploaded is not None:
    content = uploaded.getvalue()
    if st.button("Process upload", type="primary"):
        with st.spinner("Classifying, parsing, normalizing..."):
            try:
                result = ingest_upload_bytes(
                    uploaded.name,
                    content,
                    api_base=API_BASE,
                    cell_id=cell_id or None,
                    ue_id=ue_id or None,
                    query=query,
                    run_rca=run_rca and workflow != "Historical RCA",
                )
            except Exception as exc:
                st.error(f"Upload failed: {exc}")
                result = None

        if result:
            ingest = result.get("ingest") or result
            st.success(ingest.get("message", "Upload complete"))

            c1, c2, c3, c4 = st.columns(4)
            clf = ingest.get("classification", {})
            c1.metric("Detected type", clf.get("file_type", "—"))
            c2.metric("Confidence", f"{float(clf.get('confidence', 0)):.0%}")
            c3.metric("Events", ingest.get("event_count", 0))
            c4.metric("Failures", ingest.get("failure_count", 0))

            st.subheader("Classification signals")
            st.write(clf.get("signals", []))
            if clf.get("protocol_hints"):
                st.write("Protocol hints:", ", ".join(clf["protocol_hints"]))

            left, right = st.columns(2)
            with left:
                st.subheader("Detected cell IDs")
                st.write(ingest.get("cell_ids") or ["—"])
            with right:
                st.subheader("Detected UE IDs")
                st.write(ingest.get("ue_ids") or ["—"])

            schema = ingest.get("schema_info") or ingest.get("schema", {})
            if schema.get("columns"):
                st.subheader("Detected schema")
                st.json({"columns": schema.get("columns"), "column_map": schema.get("column_map")})

            if ingest.get("failures_preview"):
                st.subheader("Detected failures")
                st.dataframe(pd.DataFrame(ingest["failures_preview"]), use_container_width=True)
            elif ingest.get("events_preview"):
                st.subheader("Detected events")
                st.dataframe(pd.DataFrame(ingest["events_preview"]), use_container_width=True)

            if result.get("rca") and run_rca:
                rca = result["rca"]
                st.subheader("RCA findings")
                st.write(f"Issue type: **{rca.get('issue_type', '—')}** · Agents: {', '.join(rca.get('agents_run', []))}")
                causes = rca.get("probable_root_causes") or []
                if causes:
                    st.dataframe(pd.DataFrame(causes), use_container_width=True)
                actions = rca.get("recommended_actions") or []
                if actions:
                    st.subheader("Recommended actions")
                    for a in actions[:8]:
                        st.write(f"- {a}")

st.divider()
st.subheader("Upload history")
history = list_upload_history(api_base=API_BASE)
if history:
    hist_df = pd.DataFrame(history)
    st.dataframe(hist_df, use_container_width=True, hide_index=True)

    selected = st.selectbox(
        "Re-run RCA on historical upload",
        [u["upload_id"] for u in history],
        format_func=lambda x: next(
            (f"{u['upload_id']} — {u['filename']} ({u['file_type']})" for u in history if u["upload_id"] == x),
            x,
        ),
    )
    if st.button("Run historical RCA"):
        wf = workflow.lower().replace(" ", "_")
        with st.spinner("Running RCA..."):
            rca_result = run_upload_rca(
                selected,
                api_base=API_BASE,
                cell_id=cell_id or None,
                ue_id=ue_id or None,
                query=query,
                workflow=wf,
            )
        if rca_result.get("rca"):
            st.json(rca_result["rca"].get("probable_root_causes", [])[:5])
else:
    st.info("No uploads yet — drop a file above to begin.")
