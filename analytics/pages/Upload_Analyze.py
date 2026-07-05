"""Upload & Analyze — classify, ingest, and run RCA on telecom files."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# analytics/pages/Upload_Analyze.py → repo root
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

_DATASETS = ROOT / "datasets"
if _DATASETS.exists():
    os.environ.setdefault("TNIC_DATASETS_DIR", str(_DATASETS))
os.environ.setdefault("TNIC_ENABLE_CHROMA", "0")

st.set_page_config(page_title="Upload & Analyze", layout="wide", page_icon="📤")
st.title("📤 Upload & Analyze")
st.caption(
    "Upload CSV · XLSX · JSON · TXT · LOG · PCAP · ZIP — "
    "auto classify → normalize events → dynamic RCA"
)

ALLOWED_TYPES = ["csv", "xlsx", "xls", "json", "txt", "log", "pcap", "zip"]


def _ingest_and_rca(
    filename: str,
    content: bytes,
    *,
    cell_id: str | None,
    ue_id: str | None,
    query: str,
    run_rca: bool,
) -> dict:
    if run_rca:
        from tnic.services.dynamic_rca import ingest_and_run_rca

        return ingest_and_run_rca(
            filename,
            content,
            cell_id=cell_id or None,
            ue_id=ue_id or None,
            query=query,
        ).model_dump()
    from tnic.services.ingest_pipeline import ingest_uploaded_bytes

    ingest = ingest_uploaded_bytes(filename, content)
    return {"ingest": ingest.model_dump()}


def _list_uploads(limit: int = 20) -> list[dict]:
    from tnic.services.event_repository import list_uploads

    return [u.model_dump() for u in list_uploads(limit=limit)]


def _run_historical_rca(
    upload_id: str,
    *,
    cell_id: str | None,
    ue_id: str | None,
    query: str,
    workflow: str,
) -> dict:
    from tnic.services.dynamic_rca import run_dynamic_rca

    return run_dynamic_rca(
        upload_id,
        cell_id=cell_id or None,
        ue_id=ue_id or None,
        query=query,
        workflow=workflow,
    ).model_dump()


with st.sidebar:
    st.markdown("### Options")
    api_mode = st.checkbox("Use FastAPI backend (if running)", value=False)
    api_base = st.text_input("API base URL", value="http://127.0.0.1:8000/api/v1", disabled=not api_mode)

workflow = st.radio(
    "RCA workflow",
    ["New Upload RCA", "Historical RCA", "Single Cell RCA", "Single UE RCA"],
    horizontal=False,
)

uploaded = st.file_uploader(
    "Upload telecom file",
    type=ALLOWED_TYPES,
    accept_multiple_files=False,
)

col_a, col_b = st.columns(2)
with col_a:
    cell_id = st.text_input("Cell ID (optional)", value="", placeholder="XYZ401")
with col_b:
    ue_id = st.text_input("UE ID (optional)", value="")

query = st.text_input(
    "RCA query (optional)",
    value="",
    placeholder="handover failure cell XYZ401",
)
run_rca_after = st.checkbox("Run RCA automatically after upload", value=True)

if uploaded is not None and st.button("Process upload", type="primary"):
    content = uploaded.getvalue()
    wf = workflow.lower().replace(" ", "_")
    do_rca = run_rca_after and workflow != "Historical RCA"

    with st.spinner("Classifying, parsing, normalizing..."):
        try:
            if api_mode:
                import requests

                if do_rca:
                    files = {"file": (uploaded.name, content)}
                    data = {"query": query, "generate_report": "false"}
                    if cell_id:
                        data["cell_id"] = cell_id
                    if ue_id:
                        data["ue_id"] = ue_id
                    r = requests.post(
                        f"{api_base.rstrip('/')}/upload/rca",
                        files=files,
                        data=data,
                        timeout=120,
                    )
                    r.raise_for_status()
                    result = r.json()
                else:
                    r = requests.post(
                        f"{api_base.rstrip('/')}/upload",
                        files={"file": (uploaded.name, content)},
                        timeout=120,
                    )
                    r.raise_for_status()
                    result = {"ingest": r.json()}
            else:
                result = _ingest_and_rca(
                    uploaded.name,
                    content,
                    cell_id=cell_id or None,
                    ue_id=ue_id or None,
                    query=query,
                    run_rca=do_rca,
                )
        except Exception as exc:
            st.error(f"Upload failed: {exc}")
            result = None

    if result:
        ingest = result.get("ingest") or result
        st.success(ingest.get("message", "Upload complete"))

        clf = ingest.get("classification", {})
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Detected type", clf.get("file_type", "—"))
        c2.metric("Confidence", f"{float(clf.get('confidence', 0)):.0%}")
        c3.metric("Events", ingest.get("event_count", 0))
        c4.metric("Failures", ingest.get("failure_count", 0))

        if clf.get("signals"):
            st.write("**Signals:**", ", ".join(clf["signals"]))
        if clf.get("protocol_hints"):
            st.write("**Protocol hints:**", ", ".join(clf["protocol_hints"]))

        left, right = st.columns(2)
        with left:
            st.subheader("Detected cell IDs")
            st.write(ingest.get("cell_ids") or ["—"])
        with right:
            st.subheader("Detected UE IDs")
            st.write(ingest.get("ue_ids") or ["—"])

        schema = ingest.get("schema_info") or ingest.get("schema", {})
        if schema.get("columns"):
            with st.expander("Detected schema"):
                st.json({"columns": schema.get("columns"), "column_map": schema.get("column_map")})

        if ingest.get("failures_preview"):
            st.subheader("Detected failures")
            st.dataframe(pd.DataFrame(ingest["failures_preview"]), use_container_width=True, hide_index=True)
        elif ingest.get("events_preview"):
            st.subheader("Event preview")
            st.dataframe(pd.DataFrame(ingest["events_preview"]), use_container_width=True, hide_index=True)

        if result.get("rca") and do_rca:
            rca = result["rca"]
            st.subheader("RCA findings")
            st.write(
                f"Issue type: **{rca.get('issue_type', '—')}** · "
                f"Health: **{rca.get('health_score', '—')}** · "
                f"Agents: {', '.join(rca.get('agents_run', []))}"
            )
            causes = rca.get("probable_root_causes") or []
            if causes:
                st.dataframe(pd.DataFrame(causes), use_container_width=True, hide_index=True)
            actions = rca.get("recommended_actions") or []
            if actions:
                st.subheader("Recommended actions")
                for action in actions[:10]:
                    st.write(f"- {action}")

st.divider()
st.subheader("Upload history")

try:
    if api_mode:
        import requests

        r = requests.get(f"{api_base.rstrip('/')}/uploads", params={"limit": 20}, timeout=30)
        r.raise_for_status()
        history = r.json().get("uploads", [])
    else:
        history = _list_uploads(limit=20)
except Exception:
    history = _list_uploads(limit=20)

if history:
    st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)

    selected = st.selectbox(
        "Re-run RCA on historical upload",
        [u["upload_id"] for u in history],
        format_func=lambda x: next(
            (f"{u['upload_id']} — {u.get('filename', '?')} ({u.get('file_type', '?')})" for u in history if u["upload_id"] == x),
            x,
        ),
    )
    if st.button("Run historical RCA"):
        wf_key = workflow.lower().replace(" ", "_")
        with st.spinner("Running RCA..."):
            try:
                if api_mode:
                    import requests

                    params: dict[str, str] = {"query": query, "workflow": wf_key}
                    if cell_id:
                        params["cell_id"] = cell_id
                    if ue_id:
                        params["ue_id"] = ue_id
                    r = requests.post(
                        f"{api_base.rstrip('/')}/upload/{selected}/rca",
                        params=params,
                        timeout=120,
                    )
                    r.raise_for_status()
                    rca_result = r.json()
                else:
                    rca_result = _run_historical_rca(
                        selected,
                        cell_id=cell_id or None,
                        ue_id=ue_id or None,
                        query=query,
                        workflow=wf_key,
                    )
            except Exception as exc:
                st.error(f"RCA failed: {exc}")
                rca_result = None

        if rca_result and rca_result.get("rca"):
            rca = rca_result["rca"]
            st.write(f"Issue: **{rca.get('issue_type', '—')}**")
            causes = rca.get("probable_root_causes") or []
            if causes:
                st.dataframe(pd.DataFrame(causes), use_container_width=True, hide_index=True)
else:
    st.info("No uploads yet — drop a file above to begin.")

st.divider()
st.markdown(
    "**Tip:** Use the sidebar page **Upload & Analyze** from the main Analytics app, "
    "or call `POST /api/v1/upload/rca` when the FastAPI backend is running."
)
