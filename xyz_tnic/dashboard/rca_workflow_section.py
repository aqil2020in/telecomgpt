"""Executive AI-Powered RCA Workflow section for the home dashboard."""

from __future__ import annotations

import streamlit as st

# Specialist agents shown on the home page (icon, label, domain, one-line value)
AGENT_CARDS: list[tuple[str, str, str, str]] = [
    ("🔀", "Handover", "Mobility", "HO prep/exec failures, too-early/late, ping-pong"),
    ("📡", "RLF", "Radio", "Out-of-sync, T310 expiry, coverage-driven RLF"),
    ("📵", "Call Drop", "Session", "Drop classification — RF vs core vs mobility"),
    ("📶", "RACH", "Access", "PRACH detection, Msg3, contention failures"),
    ("⚡", "Throughput", "Capacity", "PRB, MCS, BLER, scheduler bottlenecks"),
    ("📡", "Beamforming", "Massive MIMO", "SSB utilization, beam gaps, switch stress"),
    ("📞", "VoNR", "Voice", "5QI-1 bearer, MOS, IMS/SMF session path"),
    ("🔗", "ANR", "Neighbors", "PCI conflict, missing NCL, ANR add/remove"),
    ("⚙️", "Config Audit", "CM", "Golden vs live drift — A3, TTT, PRACH"),
    ("📋", "gNB Syslog", "RAN logs", "DU/CU, NGAP, XnAP, F1 transport faults"),
    ("🚨", "Alarm Correlation", "FM", "Critical alarm chains, transport vs RF"),
    ("📱", "UE Protocol", "UE trace", "PHY→NAS failure stage localization"),
    ("🗺️", "RF Coverage", "Geospatial", "RSRP/SINR holes, beam congestion, drive test"),
]

EVIDENCE_WEIGHTS: list[tuple[str, str, str]] = [
    ("Rule confidence", "Base score", "Each fired rule carries a calibrated confidence (0–1) from threshold severity and KPI deviation."),
    ("Primary domain +10%", "Boost", "Findings in the classified issue domain (e.g. HO for handover queries) rank higher."),
    ("Classifier +15%", "Boost", "Drop/HO classifiers add evidence when KPI patterns match known failure modes."),
    ("UE trace −12%", "Supporting", "UE protocol findings support the narrative unless the query is UE-specific."),
    ("Assurance datasets", "Enrichment", "Syslog, CM, ANR, VoNR, and FM alarms inject cross-domain evidence blocks."),
    ("Coverage correlation", "Causal chain", "RF holes propagate to HO, RLF, RACH, throughput, and VoNR findings."),
]

JOURNEY_STEPS: list[tuple[str, str, str]] = [
    ("1", "Operator query", "“Handover failure cell XYZ401” — KPIs merged from PM, HO, RLF, and assurance datasets."),
    ("2", "Issue classifier", "Detects primary domain `handover`; selects agent chain from 28-type RCA catalog."),
    ("3", "Multi-agent fan-out", "HO, RLF, ANR, syslog, alarm, and RF coverage agents run in parallel."),
    ("4", "Evidence enrichment", "Coverage correlation links weak RSRP → HO prep failure; assurance adds CM drift."),
    ("5", "Master RCA ranking", "Top cause: Coverage Deficiency (52/100) + Beam Congestion — confidence 94%."),
    ("6", "Action plan", "Retilt sectors, fill holes, rebalance SSB beams 3–4; validate HO/RACH KPIs post-fix."),
]

DEMO_SCOPE: list[str] = [
    "10 demo cells (XYZ401–XYZ410) with synthetic PM, HO, RLF, RACH, throughput, and assurance data",
    "12 specialist agents + Master RCA orchestrator with 28-type RCA catalog",
    "Handover enrichment layer (33-column RCA-ready dataset, 18 HO rules)",
    "RF Coverage geospatial agent with Plotly heatmaps and coverage-hole detection",
    "Upload & classify pipeline — CSV, syslog, UE trace → ingest → dynamic RCA",
    "Streamlit multipage dashboard + FastAPI (`/api/v1/analyze/rca`)",
]

ROADMAP: list[tuple[str, str, str, str]] = [
    ("Phase 1", "Now", "Demo / pilot", "Synthetic & scrubbed exports · web dashboard · agent trace on every answer"),
    ("Phase 2", "Q3 2026", "OSS read", "Scheduled PM/FM/CM exports · Nokia NetAct / Ericsson ENM CSV & REST adapters"),
    ("Phase 3", "Q4 2026", "Near-real-time", "Alarm streaming · syslog tail · ticket webhook (ServiceNow / Remedy)"),
    ("Phase 4", "2027", "Closed loop", "CM change validation · auto work-order · post-fix KPI verification window"),
]


def _card(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


def render_rca_workflow_section() -> None:
    """Render the executive AI-Powered RCA Workflow block."""
    st.markdown(
        """
        <style>
        .rca-hero {
            background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 55%, #1d4ed8 100%);
            color: #f8fafc;
            padding: 1.6rem 1.8rem;
            border-radius: 14px;
            margin-bottom: 1.2rem;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.18);
        }
        .rca-hero h2 { margin: 0 0 0.4rem 0; font-size: 1.55rem; }
        .rca-hero p { margin: 0; opacity: 0.92; font-size: 0.98rem; line-height: 1.5; }
        .rca-flow {
            display: flex; flex-wrap: wrap; gap: 0.55rem; align-items: stretch;
            margin: 1rem 0 1.4rem 0;
        }
        .rca-step {
            flex: 1 1 120px; min-width: 110px;
            background: #f8fafc; border: 1px solid #e2e8f0;
            border-radius: 10px; padding: 0.75rem 0.65rem; text-align: center;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.06);
        }
        .rca-step .num {
            display: inline-block; width: 1.6rem; height: 1.6rem; line-height: 1.6rem;
            border-radius: 50%; background: #2563eb; color: #fff; font-weight: 700;
            font-size: 0.8rem; margin-bottom: 0.35rem;
        }
        .rca-step .lbl { font-size: 0.78rem; font-weight: 600; color: #0f172a; }
        .rca-step .sub { font-size: 0.68rem; color: #64748b; margin-top: 0.2rem; }
        .rca-arrow { align-self: center; color: #94a3b8; font-size: 1.1rem; font-weight: 700; }
        .agent-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(175px, 1fr));
            gap: 0.65rem;
            margin: 0.6rem 0 1rem 0;
        }
        .agent-card {
            background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px;
            padding: 0.75rem 0.8rem; border-left: 4px solid #2563eb;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
        }
        .agent-card .icon { font-size: 1.35rem; }
        .agent-card .name { font-weight: 700; color: #0f172a; font-size: 0.88rem; }
        .agent-card .domain {
            display: inline-block; font-size: 0.65rem; font-weight: 600;
            color: #1d4ed8; background: #eff6ff; padding: 0.1rem 0.4rem;
            border-radius: 4px; margin: 0.2rem 0;
        }
        .agent-card .desc { font-size: 0.72rem; color: #475569; line-height: 1.35; }
        .rca-panel {
            background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px;
            padding: 1rem 1.1rem; margin-bottom: 0.9rem;
        }
        .rca-panel h4 { margin: 0 0 0.5rem 0; color: #0f172a; font-size: 0.95rem; }
        .weight-row {
            display: flex; gap: 0.6rem; align-items: flex-start;
            padding: 0.45rem 0; border-bottom: 1px solid #e2e8f0;
        }
        .weight-row:last-child { border-bottom: none; }
        .weight-badge {
            flex: 0 0 auto; font-size: 0.62rem; font-weight: 700; text-transform: uppercase;
            padding: 0.15rem 0.45rem; border-radius: 4px; min-width: 4.5rem; text-align: center;
        }
        .badge-base { background: #e0e7ff; color: #3730a3; }
        .badge-boost { background: #dcfce7; color: #166534; }
        .badge-support { background: #fef3c7; color: #92400e; }
        .badge-enrich { background: #fce7f3; color: #9d174d; }
        .badge-causal { background: #e0f2fe; color: #075985; }
        .journey-step {
            display: flex; gap: 0.75rem; align-items: flex-start;
            padding: 0.55rem 0; border-left: 3px solid #2563eb;
            margin-left: 0.4rem; padding-left: 0.85rem; margin-bottom: 0.35rem;
        }
        .journey-num {
            flex: 0 0 auto; width: 1.5rem; height: 1.5rem; line-height: 1.5rem;
            text-align: center; border-radius: 50%; background: #1d4ed8; color: #fff;
            font-size: 0.72rem; font-weight: 700;
        }
        .scope-list li { margin-bottom: 0.35rem; color: #334155; font-size: 0.85rem; }
        .roadmap-row {
            display: grid; grid-template-columns: 90px 80px 1fr 2fr; gap: 0.5rem;
            padding: 0.55rem 0.65rem; border-radius: 8px; margin-bottom: 0.4rem;
            background: #fff; border: 1px solid #e2e8f0; font-size: 0.8rem;
        }
        .roadmap-row .phase { font-weight: 700; color: #1d4ed8; }
        .roadmap-row .when { color: #64748b; }
        .roadmap-row .title { font-weight: 600; color: #0f172a; }
        .roadmap-row .detail { color: #475569; }
        .corr-box {
            background: linear-gradient(90deg, #eff6ff, #f0fdf4);
            border: 1px solid #bfdbfe; border-radius: 10px;
            padding: 0.85rem 1rem; font-size: 0.82rem; color: #1e293b; line-height: 1.5;
        }
        .master-box {
            background: linear-gradient(135deg, #1e3a5f, #0f172a);
            color: #e2e8f0; border-radius: 12px; padding: 1rem 1.1rem;
            font-size: 0.84rem; line-height: 1.55;
        }
        .master-box strong { color: #93c5fd; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("🤖 AI-Powered RCA Workflow")
    _card(
        """
        <div class="rca-hero">
            <h2>Multi-Agent Root Cause Analysis</h2>
            <p>
                TNIC coordinates <strong>12 specialist agents</strong> and a <strong>Master RCA orchestrator</strong>
                to turn KPIs, drive-test data, syslog, CM, and alarms into ranked root causes,
                correlated impacts, and operator-ready action plans — with full agent traceability.
            </p>
        </div>
        """
    )

    st.markdown("#### End-to-end workflow")
    flow_steps = [
        ("1", "Query & KPIs", "PM · HO · RLF · assurance"),
        ("2", "Classifier", "28 RCA types"),
        ("3", "Agent fan-out", "12 specialists"),
        ("4", "Enrichment", "Coverage · UE · FM"),
        ("5", "Correlation", "Cross-domain"),
        ("6", "Ranking", "Confidence score"),
        ("7", "Report", "Narrative + checklist"),
    ]
    steps_html = ""
    for i, (num, lbl, sub) in enumerate(flow_steps):
        if i > 0:
            steps_html += '<div class="rca-arrow">→</div>'
        steps_html += (
            f'<div class="rca-step"><div class="num">{num}</div>'
            f'<div class="lbl">{lbl}</div><div class="sub">{sub}</div></div>'
        )
    _card(f'<div class="rca-flow">{steps_html}</div>')

    st.markdown("#### Specialist AI agents")
    cards_html = '<div class="agent-grid">'
    for icon, name, domain, desc in AGENT_CARDS:
        cards_html += (
            f'<div class="agent-card"><div class="icon">{icon}</div>'
            f'<div class="name">{name}</div>'
            f'<span class="domain">{domain}</span>'
            f'<div class="desc">{desc}</div></div>'
        )
    cards_html += "</div>"
    _card(cards_html)

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("#### How evidence is weighted")
        rows = ""
        badge_map = {
            "Base score": "badge-base",
            "Boost": "badge-boost",
            "Supporting": "badge-support",
            "Enrichment": "badge-enrich",
            "Causal chain": "badge-causal",
        }
        for label, kind, detail in EVIDENCE_WEIGHTS:
            badge_cls = badge_map.get(kind, "badge-base")
            rows += (
                f'<div class="weight-row">'
                f'<span class="weight-badge {badge_cls}">{kind}</span>'
                f'<div><strong>{label}</strong><br/><span style="color:#64748b;font-size:0.78rem;">{detail}</span></div>'
                f"</div>"
            )
        _card(f'<div class="rca-panel"><h4>Scoring model</h4>{rows}</div>')

        st.markdown("#### How agents correlate findings")
        _card(
            """
            <div class="corr-box">
                <strong>Coverage → mobility chain:</strong> RF holes at cell edge drive HO prep failures,
                RLF, RACH access issues, throughput collapse, and VoNR bearer instability.<br/><br/>
                <strong>Workflow templates:</strong> Call-drop, HO-failure, RACH, throughput, VoNR, and
                cell-outage workflows inject cross-domain checks (ANR neighbors, CM drift, transport).<br/><br/>
                <strong>Assurance fusion:</strong> gNB syslog, config audit, FM alarms, and UE protocol traces
                are merged into a single evidence graph for the Master RCA narrative.
            </div>
            """
        )

    with col_r:
        st.markdown("#### How Master RCA determines root cause")
        _card(
            """
            <div class="master-box">
                <strong>1. Classify</strong> — Parse query + KPIs; detect issue type and RCA catalog entry.<br/>
                <strong>2. Orchestrate</strong> — Fan out to domain-specific agent chain
                (e.g. HO → RLF → ANR → syslog → alarm → RF coverage).<br/>
                <strong>3. Enrich</strong> — <code>enrich_master_rca()</code> adds coverage correlation,
                workflow blocks, assurance evidence, and UE failure localization.<br/>
                <strong>4. Rank</strong> — Sort by adjusted confidence: primary-domain +10%,
                classifier +15%, UE supporting −12%.<br/>
                <strong>5. Deliver</strong> — Top-5 probable causes, deduplicated actions,
                validation checklist, health score, and optional LLM narrative report.
            </div>
            """
        )

        st.markdown("#### Example RCA journey — XYZ401")
        journey_html = ""
        for num, title, detail in JOURNEY_STEPS:
            journey_html += (
                f'<div class="journey-step">'
                f'<div class="journey-num">{num}</div>'
                f'<div><strong>{title}</strong><br/>'
                f'<span style="color:#475569;font-size:0.8rem;">{detail}</span></div></div>'
            )
        _card(f'<div class="rca-panel">{journey_html}</div>')

    st.markdown("#### Current demo scope")
    scope_items = "".join(f"<li>{item}</li>" for item in DEMO_SCOPE)
    _card(f'<div class="rca-panel"><ul class="scope-list">{scope_items}</ul></div>')

    st.markdown("#### Future OSS / NetAct integration roadmap")
    roadmap_html = ""
    for phase, when, title, detail in ROADMAP:
        roadmap_html += (
            f'<div class="roadmap-row">'
            f'<span class="phase">{phase}</span>'
            f'<span class="when">{when}</span>'
            f'<span class="title">{title}</span>'
            f'<span class="detail">{detail}</span></div>'
        )
    _card(roadmap_html)

    st.caption(
        "Architecture reference: docs/RCA_AGENT_END_TO_END_HANDOVER.md · "
        "Live RCA: sidebar **RCA Report** or **Assurance Hub**"
    )
