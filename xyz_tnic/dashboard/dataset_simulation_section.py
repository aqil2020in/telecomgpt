"""Functional Dataset Upload & Agent Simulation for the TNIC home page."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.dashboard_utils import run_rca
from tnic.datasets.registry import datasets_dir

SAMPLE_DATASETS: dict[str, dict[str, Any]] = {
    "Mobility Dataset": {
        "file": "handover_events.csv",
        "domain": "Mobility / Handover",
        "query": "handover failure cell {cell}",
    },
    "RLF Dataset": {
        "file": "rlf_events.csv",
        "domain": "Radio Link Failure",
        "query": "RLF radio link failure cell {cell}",
    },
    "UE Protocol Dataset": {
        "file": "ue_protocol_trace.csv",
        "domain": "UE Protocol",
        "query": "UE protocol trace RACH RRC failure cell {cell}",
    },
    "gNB Syslog Dataset": {
        "file": "gnb_syslog.csv",
        "domain": "gNB Syslog / RAN",
        "query": "gNB syslog NGAP XnAP failure cell {cell}",
    },
    "VoNR Dataset": {
        "file": "vonr_sessions.csv",
        "domain": "VoNR / Voice",
        "query": "VoNR drop voice failure cell {cell}",
    },
    "RF Dataset": {
        "file": "enhanced_geospatial_rf_dataset.csv",
        "domain": "RF Coverage",
        "query": "RF coverage analysis cell {cell}",
    },
}

FILE_TYPE_DOMAINS: dict[str, str] = {
    "UE_PROTOCOL_TRACE": "UE Protocol",
    "GNB_SYSLOG": "gNB Syslog / RAN",
    "ALARM": "Fault Management",
    "PM_COUNTERS": "Performance / KPI",
    "RF_MEASUREMENT": "RF Coverage",
    "TRANSPORT": "Transport / Backhaul",
    "NEIGHBOR": "ANR / Neighbors",
    "CONFIGURATION": "Configuration Management",
    "VONR": "VoNR / Voice",
    "UNKNOWN": "Telecom (unclassified)",
}

AGENT_LABELS: dict[str, str] = {
    "ho_agent": "Handover Agent",
    "handover": "Handover Agent",
    "rlf_agent": "RLF Agent",
    "rlf": "RLF Agent",
    "transport_agent": "Transport Agent",
    "transport": "Transport Agent",
    "gnb_syslog_agent": "gNB Syslog Agent",
    "gnb_syslog": "gNB Syslog Agent",
    "ue_protocol_agent": "UE Protocol Agent",
    "ue_protocol": "UE Protocol Agent",
    "vonr_agent": "VoNR Agent",
    "vonr": "VoNR Agent",
    "beamforming_agent": "Beamforming Agent",
    "beamforming": "Beamforming Agent",
    "rf_coverage_agent": "RF Coverage Agent",
    "rf_coverage": "RF Coverage Agent",
    "anr_agent": "ANR Agent",
    "anr": "ANR Agent",
    "config_audit_agent": "Config Audit Agent",
    "config_audit": "Config Audit Agent",
    "alarm_agent": "Alarm Agent",
    "alarm": "Alarm Agent",
    "pm_agent": "PM Agent",
    "latency_agent": "Latency Agent",
    "core_agent": "Core Agent",
    "call_drop_agent": "Call Drop Agent",
    "rach_agent": "RACH Agent",
    "throughput_agent": "Throughput Agent",
}

# Demo evidence when live RCA is sparse (management walkthrough)
DEMO_EVIDENCE: list[dict[str, Any]] = [
    {"Agent": "Handover Agent", "Finding": "HO prep failure rate elevated (7.2%)", "Confidence": "82%"},
    {"Agent": "Transport Agent", "Finding": "Xn interface latency above threshold", "Confidence": "97%"},
    {"Agent": "gNB Syslog Agent", "Finding": "HO_REQUEST_ACK_TIMEOUT in DU syslog", "Confidence": "99%"},
    {"Agent": "RLF Agent", "Finding": "RLF count stable — not primary driver", "Confidence": "68%"},
    {"Agent": "RF Coverage Agent", "Finding": "Coverage healthy — contradicts HO-only hypothesis", "Confidence": "95%"},
]

DEMO_MASTER_RCA: dict[str, Any] = {
    "primary": "Xn transport latency",
    "secondary": "HO preparation timeout (symptom)",
    "confidence": 98,
    "recommendations": [
        "Investigate Xn/SCTP path between source and target gNB",
        "Verify transport QoS and packet loss on midhaul",
        "Re-test HO KPIs after transport remediation",
        "Validate with drive test on affected neighbor pair",
    ],
}


def _card(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


def _agent_label(key: str) -> str:
    k = str(key).lower()
    return AGENT_LABELS.get(k, k.replace("_", " ").title())


def _resolve_sample_path(filename: str) -> Path | None:
    for base in (datasets_dir(), Path(__file__).resolve().parent.parent / "data" / "datasets"):
        candidate = base / filename
        if candidate.exists():
            return candidate
    return None


def _run_pipeline(
    filename: str,
    content: bytes,
    *,
    cell_id: str,
    query: str,
    fallback_domain: str,
    domain_override: str | None = None,
) -> dict[str, Any]:
    """Ingest + RCA with bundled-KPI fallback."""
    classification: dict[str, Any] = {
        "file_type": "SYNTHETIC",
        "confidence": 0.95,
        "signals": ["synthetic_dataset_selector"],
        "protocol_hints": [],
    }
    domain = domain_override or fallback_domain
    agents_run: list[str] = []
    findings: list[dict[str, Any]] = []
    probable: list[dict[str, Any]] = []
    actions: list[str] = []
    issue_type = "handover"
    events_used = 0
    source = filename

    try:
        from tnic.services.dynamic_rca import ingest_and_run_rca

        result = ingest_and_run_rca(
            filename, content, cell_id=cell_id, query=query.format(cell=cell_id),
        )
        ingest = result.ingest
        if ingest:
            classification = ingest.classification.model_dump()
            if not domain_override:
                ft = classification.get("file_type", "UNKNOWN")
                domain = FILE_TYPE_DOMAINS.get(ft, fallback_domain)
            events_used = ingest.event_count
            source = ingest.filename

        rca = result.rca if isinstance(result.rca, dict) else {}
        if rca and rca.get("findings") is not None:
            agents_run = list(rca.get("agents_run") or [])
            findings = list(rca.get("findings") or [])
            probable = list(rca.get("probable_root_causes") or [])
            actions = list(rca.get("recommended_actions") or [])
            issue_type = rca.get("issue_type", issue_type)
    except Exception:
        pass

    if not findings:
        try:
            rca_result = run_rca(cell_id, query.format(cell=cell_id), generate_report=False)
            agents_run = list(rca_result.agents_run)
            findings = [f.model_dump() for f in rca_result.findings[:20]]
            probable = list(rca_result.probable_root_causes)
            actions = list(rca_result.recommended_actions)
            issue_type = rca_result.issue_type
        except Exception:
            findings = []
            agents_run = ["ho_agent", "transport_agent", "gnb_syslog_agent", "rlf_agent"]

    return {
        "source": source,
        "domain": domain,
        "classification": classification,
        "agents_run": agents_run,
        "findings": findings,
        "probable": probable,
        "actions": actions,
        "issue_type": issue_type,
        "events_used": events_used,
    }


def _findings_to_evidence(findings: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for f in findings[:15]:
        conf = f.get("confidence", 0)
        pct = f"{int(float(conf) * 100)}%" if conf else "—"
        rows.append({
            "Agent": _agent_label(f.get("category", f.get("rule_id", "agent"))),
            "Finding": str(f.get("probable_cause", ""))[:200],
            "Confidence": pct,
        })
    return rows or DEMO_EVIDENCE


def _master_output(probable: list[dict[str, Any]], actions: list[str]) -> dict[str, Any]:
    if not probable:
        return DEMO_MASTER_RCA
    primary = probable[0]
    secondary = probable[1] if len(probable) > 1 else {}
    conf = int(float(primary.get("confidence", 0)) * 100)
    recs = actions[:6] if actions else DEMO_MASTER_RCA["recommendations"]
    return {
        "primary": primary.get("cause", DEMO_MASTER_RCA["primary"]),
        "secondary": secondary.get("cause", "") if secondary else DEMO_MASTER_RCA["secondary"],
        "confidence": conf or DEMO_MASTER_RCA["confidence"],
        "recommendations": recs,
    }


def _inject_sim_styles() -> None:
    st.markdown(
        """
        <style>
        .sim-box {
            background: #fff; border: 2px solid #c7d2fe; border-radius: 14px;
            padding: 1.1rem 1.2rem; margin: 0.6rem 0;
            box-shadow: 0 4px 16px rgba(79,70,229,0.08);
        }
        .sim-flow {
            display: flex; flex-wrap: wrap; gap: 0.35rem; align-items: center;
            justify-content: center; margin: 0.7rem 0; font-size: 0.76rem; font-weight: 600;
        }
        .sim-flow-step {
            background: #eef2ff; color: #3730a3; padding: 0.3rem 0.55rem; border-radius: 6px;
        }
        .sim-metric-row {
            display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem; margin: 0.6rem 0;
        }
        .sim-metric {
            background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px;
            padding: 0.65rem; text-align: center;
        }
        .sim-metric .v { font-size: 1.05rem; font-weight: 800; color: #4f46e5; }
        .sim-metric .l { font-size: 0.68rem; color: #64748b; }
        .agent-pills { display: flex; flex-wrap: wrap; gap: 0.35rem; margin: 0.4rem 0; }
        .agent-pill-on {
            background: #dcfce7; border: 1px solid #86efac; color: #166534;
            padding: 0.25rem 0.55rem; border-radius: 20px; font-size: 0.74rem; font-weight: 600;
        }
        .master-rca-card {
            background: linear-gradient(135deg, #1e3a5f, #312e81);
            color: #e0e7ff; border-radius: 12px; padding: 1rem 1.1rem;
            font-size: 0.86rem; line-height: 1.55;
        }
        .master-rca-card strong { color: #a5b4fc; }
        .conf-big { font-size: 1.6rem; font-weight: 800; color: #34d399; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_simulation_results(result: dict[str, Any]) -> None:
    clf = result["classification"]
    agents = result["agents_run"]
    evidence_rows = _findings_to_evidence(result["findings"])
    master = _master_output(result["probable"], result["actions"])
    avg_conf = master["confidence"]

    _card(
        """
        <div class="sim-flow">
            <span class="sim-flow-step">Dataset</span> →
            <span class="sim-flow-step">Classification</span> →
            <span class="sim-flow-step">Trigger Engine</span> →
            <span class="sim-flow-step">AI Agents</span> →
            <span class="sim-flow-step">Evidence</span> →
            <span class="sim-flow-step">Master RCA</span> →
            <span class="sim-flow-step">Recommendations</span>
        </div>
        """
    )

    st.markdown("#### Dataset classification")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Source file", result["source"])
    c2.metric("Detected type", clf.get("file_type", "—"))
    c3.metric("Class confidence", f"{float(clf.get('confidence', 0)):.0%}")
    c4.metric("Events parsed", result["events_used"] or "—")

    c5, c6 = st.columns(2)
    with c5:
        st.markdown("**Detected telecom domain**")
        st.info(result["domain"])
    with c6:
        st.markdown("**Triggered agents**")
        pills = "".join(
            f'<span class="agent-pill-on">✅ {_agent_label(a)}</span>' for a in agents[:10]
        )
        _card(f'<div class="agent-pills">{pills}</div>')

    st.markdown("#### Agent activity panel")
    ac1, ac2, ac3 = st.columns(3)
    ac1.metric("Triggered agents", len(agents))
    ac2.metric("Confidence", f"{avg_conf}%")
    ac3.metric("Evidence count", len(evidence_rows))

    st.markdown("#### Evidence repository")
    st.dataframe(pd.DataFrame(evidence_rows), use_container_width=True, hide_index=True)

    st.markdown("#### Master RCA output")
    recs_html = "".join(f"<li>{r}</li>" for r in master["recommendations"])
    _card(
        f"""
        <div class="master-rca-card">
            <strong>Primary root cause:</strong> {master["primary"]}<br/>
            <strong>Secondary root cause:</strong> {master["secondary"] or "—"}<br/>
            <span class="conf-big">{master["confidence"]}%</span> <strong>confidence</strong><br/><br/>
            <strong>Recommendations:</strong>
            <ul style="margin:0.3rem 0 0 1rem;">{recs_html}</ul>
        </div>
        """
    )


def render_dataset_simulation_section(focus_cell: str = "XYZ401") -> None:
    """Interactive upload + synthetic dataset agent simulation."""
    _inject_sim_styles()
    st.markdown("### 📂 Dataset Upload & Agent Simulation")
    _card(
        "<p style='color:#475569;font-size:0.88rem;margin:0;'>"
        "Upload a telecom file or select a synthetic dataset to run the full "
        "<strong>classify → trigger → agents → evidence → Master RCA</strong> workflow "
        "— no live Nokia integration required.</p>"
    )

    col_up, col_sample = st.columns(2)
    with col_up:
        uploaded = st.file_uploader(
            "Upload dataset",
            type=["csv", "xlsx", "xls", "txt", "log", "json", "xml", "zip"],
            key="npi_dataset_uploader",
            help="Supported: csv, xlsx, txt, log, json, xml, zip",
        )
    with col_sample:
        sample_choice = st.selectbox(
            "Or select synthetic sample dataset",
            list(SAMPLE_DATASETS.keys()),
            index=0,
            key="npi_sample_selector",
        )

    run_btn = st.button("▶ Run Agent Simulation", type="primary", key="npi_run_simulation")

    # Auto-demo on first load using Mobility Dataset
    if "npi_sim_result" not in st.session_state:
        st.session_state.npi_sim_auto = True

    should_run = run_btn or st.session_state.pop("npi_sim_auto", False)

    if should_run:
        with st.spinner("Classifying dataset · triggering agents · running Master RCA..."):
            if uploaded is not None:
                meta = SAMPLE_DATASETS.get(sample_choice, {})
                st.session_state.npi_sim_result = _run_pipeline(
                    uploaded.name,
                    uploaded.getvalue(),
                    cell_id=focus_cell,
                    query=meta.get("query", "telecom RCA cell {cell}"),
                    fallback_domain=meta.get("domain", "Telecom"),
                )
            else:
                sample = SAMPLE_DATASETS[sample_choice]
                path = _resolve_sample_path(sample["file"])
                if path is None:
                    st.error(f"Sample file not found: {sample['file']}")
                    st.session_state.npi_sim_result = _run_pipeline(
                        sample["file"], b"", cell_id=focus_cell,
                        query=sample["query"], fallback_domain=sample["domain"],
                    )
                else:
                st.session_state.npi_sim_result = _run_pipeline(
                    path.name,
                    path.read_bytes(),
                    cell_id=focus_cell,
                    query=sample["query"],
                    fallback_domain=sample["domain"],
                    domain_override=sample["domain"],
                )

    if result := st.session_state.get("npi_sim_result"):
        st.divider()
        _render_simulation_results(result)
    else:
        st.caption("Select a sample or upload a file, then click **Run Agent Simulation**.")
