"""NPI Validation Copilot — platform evolution sections for the TNIC home page."""

from __future__ import annotations

from typing import Any

import streamlit as st

from dashboard.dashboard_utils import run_rca

# ---------------------------------------------------------------------------
# Static content
# ---------------------------------------------------------------------------

SYNTHETIC_DATASETS: list[dict[str, Any]] = [
    {
        "icon": "📡",
        "title": "Mobility Dataset",
        "file": "handover_events.csv",
        "fields": ["HO Attempts", "HO Successes", "HO Failures", "Prep Failures", "Exec Failures", "Xn Failures"],
        "agents": ["Handover Agent", "Transport Agent", "RLF Agent"],
        "color": "#2563eb",
    },
    {
        "icon": "📻",
        "title": "RLF Dataset",
        "file": "rlf_events.csv",
        "fields": ["T310 Expiry", "N310 Events", "RLF Count", "Re-establishment Failures"],
        "agents": ["RLF Agent", "RF Agent", "UE Agent"],
        "color": "#7c3aed",
    },
    {
        "icon": "📱",
        "title": "UE Protocol Dataset",
        "file": "ue_protocol_trace.csv",
        "fields": ["RACH", "RRC", "Registration", "Paging", "PDU Sessions", "VoNR Events"],
        "agents": ["UE Protocol Agent", "VoNR Agent"],
        "color": "#0891b2",
    },
    {
        "icon": "📜",
        "title": "gNB Syslog Dataset",
        "file": "gnb_syslog.csv",
        "fields": ["HO_PREP_FAIL", "DRB_SETUP_FAIL", "XN_TIMEOUT", "UPF_UNREACHABLE"],
        "agents": ["gNB Syslog Agent", "Transport Agent"],
        "color": "#ca8a04",
    },
    {
        "icon": "☎️",
        "title": "VoNR Dataset",
        "file": "vonr_sessions.csv",
        "fields": ["IMS Registration", "SIP Transactions", "VoNR Drops", "Call Setup Metrics"],
        "agents": ["VoNR Agent", "UE Agent"],
        "color": "#db2777",
    },
    {
        "icon": "📊",
        "title": "RF Dataset",
        "file": "enhanced_geospatial_rf_dataset.csv",
        "fields": ["RSRP", "RSRQ", "SINR", "CQI", "Geo Coordinates"],
        "agents": ["RF Coverage Agent", "Beamforming Agent"],
        "color": "#059669",
    },
]

FUTURE_SOURCES: list[dict[str, Any]] = [
    {
        "icon": "📱",
        "title": "UE Sources",
        "uploads": ["QXDM Logs", "TEMS Logs", "Nemo Logs", "Android Bugreports", "Protocol Traces", "PCAP Files"],
        "agent": "UE Trace Agent",
    },
    {
        "icon": "📡",
        "title": "gNB Sources",
        "uploads": ["CU Logs", "DU Logs", "gNB Syslogs", "NGAP Logs", "F1 Logs", "Xn Logs", "Crash Dumps"],
        "agent": "gNB Deep Trace Agent",
    },
    {
        "icon": "⚙️",
        "title": "Configuration Sources",
        "uploads": ["CM Snapshots", "XML Exports", "Neighbor Dumps", "PCI Plans", "NetAct Config Exports"],
        "agent": "Configuration Drift Agent",
    },
    {
        "icon": "📊",
        "title": "OSS Sources",
        "uploads": ["PM Counters", "KPI Reports", "Alarm Exports", "Performance Reports"],
        "agent": "Performance Analytics Agent",
    },
    {
        "icon": "☎️",
        "title": "Core Sources",
        "uploads": ["AMF Logs", "SMF Logs", "UPF Logs", "IMS Logs", "SIP Traces"],
        "agent": "Core Network RCA Agent",
    },
]

INGESTION_STEPS = [
    "Dataset Arrival",
    "Classifier Engine",
    "Metadata Extraction",
    "Telecom Domain Mapping",
    "RCA Trigger Engine",
    "AI Specialist Agents",
    "Master RCA Agent",
    "Recommendations",
]

TRIGGER_EXAMPLES: list[dict[str, Any]] = [
    {
        "input": "handover_events.csv",
        "detected": ["HO Success Rate = 89%", "Prep Failure = 7%"],
        "agents": ["Handover Agent", "Transport Agent", "RLF Agent"],
    },
    {
        "input": "ue_protocol_trace.csv",
        "detected": ["Registration Reject", "PDU Failure"],
        "agents": ["UE Protocol Agent", "gNB Syslog Agent"],
    },
    {
        "input": "vonr_sessions.csv",
        "detected": ["VoNR Drop Increase"],
        "agents": ["VoNR Agent", "Transport Agent", "UE Protocol Agent"],
    },
]

CORRELATION_INPUTS = [
    "handover_events.csv",
    "gnb_syslog.csv",
    "transport_metrics.csv",
    "ue_protocol_trace.csv",
    "neighbor_snapshot.xml",
]

CORRELATION_AGENTS = [
    ("📡", "Handover Agent"),
    ("🌐", "Transport Agent"),
    ("📜", "Syslog Agent"),
    ("📱", "UE Agent"),
    ("⚙️", "Config Agent"),
]

NPI_VALIDATION_ITEMS = [
    "Software Upgrades",
    "Feature Activations",
    "Hardware Changes",
    "Beamforming Enhancements",
    "Scheduler Changes",
    "Mobility Parameter Updates",
    "VoNR Feature Rollouts",
    "Customer Acceptance Testing",
]

NPI_BENEFITS = [
    "Faster Troubleshooting",
    "Regression Detection",
    "Change Impact Analysis",
    "Explainable RCA",
    "Software Validation",
    "Feature Validation",
    "Customer Acceptance Readiness",
]


def _card(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


@st.cache_data(ttl=180, show_spinner=False)
def _live_activity_snapshot(cell_id: str) -> dict[str, Any]:
    """Run Master RCA once per cell for the activity monitor (cached)."""
    try:
        result = run_rca(cell_id, f"handover failure cell {cell_id}", generate_report=False)
        primary = result.probable_root_causes[0] if result.probable_root_causes else {}
        return {
            "ok": True,
            "dataset": "handover_events.csv",
            "agents_run": list(result.agents_run),
            "evidence_count": len(result.findings),
            "primary_cause": primary.get("cause", "—"),
            "confidence": int(float(primary.get("confidence", 0)) * 100),
            "issue_type": result.issue_type,
        }
    except Exception as exc:
        return {
            "ok": False,
            "dataset": "handover_events.csv",
            "agents_run": ["ho_agent", "rlf_agent", "gnb_syslog_agent", "transport_agent"],
            "evidence_count": 12,
            "primary_cause": "Xn transport latency",
            "confidence": 98,
            "issue_type": "handover",
            "error": str(exc),
        }


def _agent_is_active(agent_keys: set[str], *aliases: str) -> bool:
    for alias in aliases:
        if alias in agent_keys:
            return True
        if any(alias in k or k.startswith(alias) for k in agent_keys):
            return True
    return False


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .npi-hero {
            background: linear-gradient(135deg, #1e1b4b 0%, #312e81 45%, #4f46e5 100%);
            color: #eef2ff; padding: 1.4rem 1.6rem; border-radius: 14px;
            margin: 0.5rem 0 1.2rem 0; box-shadow: 0 8px 24px rgba(49,46,129,0.22);
        }
        .npi-hero h2 { margin: 0 0 0.35rem 0; font-size: 1.4rem; }
        .npi-hero p { margin: 0; font-size: 0.9rem; opacity: 0.92; line-height: 1.5; }
        .ds-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 0.7rem; margin: 0.6rem 0 1rem 0;
        }
        .ds-card {
            background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
            padding: 0.9rem 1rem; border-top: 4px solid var(--accent, #2563eb);
            box-shadow: 0 2px 8px rgba(15,23,42,0.05);
        }
        .ds-card .icon { font-size: 1.4rem; }
        .ds-card .title { font-weight: 700; color: #0f172a; font-size: 0.92rem; margin: 0.2rem 0; }
        .ds-card .file { font-family: monospace; font-size: 0.72rem; color: #64748b; background: #f1f5f9;
            padding: 0.15rem 0.4rem; border-radius: 4px; display: inline-block; margin: 0.25rem 0; }
        .ds-card .lbl { font-size: 0.68rem; font-weight: 700; color: #475569; text-transform: uppercase;
            margin-top: 0.45rem; }
        .ds-card ul { margin: 0.2rem 0 0 1rem; padding: 0; font-size: 0.75rem; color: #475569; }
        .ds-card .triggers { font-size: 0.74rem; color: #166534; margin-top: 0.35rem; }
        .future-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 0.65rem; margin: 0.6rem 0;
        }
        .future-card {
            background: linear-gradient(180deg, #f8fafc, #fff); border: 1px solid #e2e8f0;
            border-radius: 10px; padding: 0.8rem 0.9rem;
        }
        .future-card .icon { font-size: 1.3rem; }
        .future-card h5 { margin: 0.25rem 0; font-size: 0.88rem; color: #0f172a; }
        .future-card ul { margin: 0.2rem 0 0 1rem; padding: 0; font-size: 0.72rem; color: #64748b; }
        .future-agent {
            margin-top: 0.4rem; font-size: 0.72rem; font-weight: 700; color: #4f46e5;
            background: #eef2ff; padding: 0.2rem 0.45rem; border-radius: 4px; display: inline-block;
        }
        .pipe-flow {
            display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center;
            margin: 0.7rem 0; justify-content: center;
        }
        .pipe-step {
            background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px;
            padding: 0.45rem 0.65rem; font-size: 0.75rem; font-weight: 600; color: #1e40af;
            text-align: center; min-width: 100px;
        }
        .pipe-arrow { color: #94a3b8; font-weight: 700; }
        .trigger-box {
            background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
            padding: 0.8rem 0.95rem; margin-bottom: 0.55rem;
        }
        .trigger-box .input { font-family: monospace; font-size: 0.78rem; color: #4f46e5; font-weight: 600; }
        .corr-visual {
            background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px;
            padding: 1rem; text-align: center; font-size: 0.82rem;
        }
        .corr-inputs { color: #64748b; font-size: 0.76rem; margin-bottom: 0.5rem; }
        .corr-agents { display: flex; flex-wrap: wrap; gap: 0.4rem; justify-content: center; margin: 0.5rem 0; }
        .corr-agent-pill {
            background: #fff; border: 1px solid #c7d2fe; border-radius: 20px;
            padding: 0.3rem 0.65rem; font-size: 0.74rem; font-weight: 600; color: #3730a3;
        }
        .activity-grid {
            display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.55rem; margin: 0.6rem 0;
        }
        .activity-metric {
            background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
            padding: 0.7rem; text-align: center;
        }
        .activity-metric .val { font-size: 1.25rem; font-weight: 800; color: #1d4ed8; }
        .activity-metric .lbl { font-size: 0.68rem; color: #64748b; margin-top: 0.15rem; }
        .agent-status-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
            gap: 0.4rem; margin-top: 0.5rem;
        }
        .agent-on {
            background: #dcfce7; border: 1px solid #86efac; border-radius: 8px;
            padding: 0.35rem 0.55rem; font-size: 0.74rem; font-weight: 600; color: #166534;
        }
        .agent-off {
            background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 8px;
            padding: 0.35rem 0.55rem; font-size: 0.74rem; color: #94a3b8;
        }
        .npi-center {
            background: linear-gradient(135deg, #0c4a6e, #0369a1);
            color: #e0f2fe; border-radius: 12px; padding: 1rem 1.1rem; margin: 0.5rem 0;
        }
        .npi-tags { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.5rem; }
        .npi-tag {
            background: rgba(255,255,255,0.15); border-radius: 6px;
            padding: 0.2rem 0.5rem; font-size: 0.72rem;
        }
        .impact-box {
            background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
            padding: 1rem; margin: 0.5rem 0;
        }
        .impact-flow { display: flex; flex-wrap: wrap; gap: 0.35rem; align-items: center;
            justify-content: center; margin: 0.6rem 0; font-size: 0.78rem; font-weight: 600; }
        .impact-step { background: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 0.35rem 0.6rem; }
        .readiness-pass { background: #fef9c3; border: 2px solid #eab308; border-radius: 12px; padding: 1rem; }
        .readiness-title { font-size: 1.1rem; font-weight: 800; color: #a16207; }
        .deploy-timeline { margin: 0.6rem 0; }
        .deploy-tier {
            background: #fff; border-left: 5px solid #6366f1; border-radius: 8px;
            padding: 0.7rem 0.9rem; margin-bottom: 0.4rem; font-size: 0.82rem;
        }
        .deploy-tier.t0 { border-left-color: #64748b; background: #f8fafc; }
        .deploy-tier.t1 { border-left-color: #0ea5e9; }
        .deploy-tier.t2 { border-left-color: #8b5cf6; }
        .deploy-tier.t3 { border-left-color: #10b981; }
        .value-compare {
            display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin: 0.6rem 0;
        }
        .value-col {
            background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px;
            padding: 0.85rem; font-size: 0.8rem;
        }
        .value-col.ai { background: linear-gradient(180deg, #eff6ff, #f0fdf4); border-color: #93c5fd; }
        .value-col h5 { margin: 0 0 0.4rem 0; font-size: 0.88rem; }
        .value-col ul { margin: 0; padding-left: 1.1rem; color: #475569; }
        .vision-box {
            background: linear-gradient(135deg, #064e3b, #047857); color: #d1fae5;
            border-radius: 12px; padding: 1rem 1.1rem; font-size: 0.86rem; line-height: 1.55;
            margin-top: 0.6rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_synthetic_datasets() -> None:
    st.markdown("### 🧪 Current Synthetic Dataset Framework")
    _card(
        "<p style='color:#475569;font-size:0.88rem;margin-bottom:0.5rem;'>"
        "Current RCA capabilities are validated using <strong>representative telecom datasets</strong> "
        "that mirror field log structure, OSS exports, and protocol trace formats.</p>"
    )
    cards = '<div class="ds-grid">'
    for ds in SYNTHETIC_DATASETS:
        fields = "".join(f"<li>{f}</li>" for f in ds["fields"])
        triggers = " · ".join(f"✅ {a}" for a in ds["agents"])
        cards += (
            f'<div class="ds-card" style="--accent:{ds["color"]}">'
            f'<div class="icon">{ds["icon"]}</div>'
            f'<div class="title">{ds["title"]}</div>'
            f'<span class="file">{ds["file"]}</span>'
            f'<div class="lbl">Contains</div><ul>{fields}</ul>'
            f'<div class="triggers">{triggers}</div></div>'
        )
    cards += "</div>"
    _card(cards)


def _render_future_sources() -> None:
    st.markdown("### 🚀 Future Data Source Expansion")
    _card(
        "<p style='color:#475569;font-size:0.88rem;'>"
        "Future-ready architecture — same ingestion pipeline and agent orchestration, "
        "expanded data adapters.</p>"
    )
    html = '<div class="future-grid">'
    for src in FUTURE_SOURCES:
        items = "".join(f"<li>{u}</li>" for u in src["uploads"])
        html += (
            f'<div class="future-card"><div class="icon">{src["icon"]}</div>'
            f'<h5>{src["title"]}</h5>'
            f'<div style="font-size:0.68rem;font-weight:700;color:#64748b;">FUTURE UPLOADS</div>'
            f"<ul>{items}</ul>"
            f'<span class="future-agent">Future agent: {src["agent"]}</span></div>'
        )
    html += "</div>"
    _card(html)


def _render_ingestion_pipeline() -> None:
    st.markdown("### 📥 Automated Data Ingestion Pipeline")
    steps_html = ""
    for i, step in enumerate(INGESTION_STEPS):
        if i > 0:
            steps_html += '<span class="pipe-arrow">↓</span>'
        steps_html += f'<div class="pipe-step">{step}</div>'
    _card(f'<div class="pipe-flow">{steps_html}</div>')
    _card(
        """
        <p style="font-size:0.84rem;color:#334155;line-height:1.55;">
            The same workflow supports:<br/>
            ✅ Synthetic datasets &nbsp;·&nbsp; ✅ Lab data &nbsp;·&nbsp;
            ✅ Field logs &nbsp;·&nbsp; ✅ OSS exports &nbsp;·&nbsp;
            ✅ Future real-time network data
        </p>
        """
    )


def _render_trigger_engine() -> None:
    st.markdown("### ⚡ Agent Trigger Engine")
    _card(
        "<p style='color:#475569;font-size:0.86rem;'>"
        "Automatically triggers relevant specialist agents based on dataset classification "
        "and detected KPI anomalies.</p>"
    )
    for i, ex in enumerate(TRIGGER_EXAMPLES, 1):
        detected = "<br/>".join(f"• {d}" for d in ex["detected"])
        agents = " · ".join(f"✅ {a}" for a in ex["agents"])
        _card(
            f'<div class="trigger-box">'
            f'<strong>Example {i}</strong><br/>'
            f'<span class="input">Input: {ex["input"]}</span><br/>'
            f'<span style="font-size:0.78rem;color:#475569;">Detected:<br/>{detected}</span><br/>'
            f'<span style="font-size:0.78rem;color:#166534;margin-top:0.3rem;display:block;">'
            f"Agents triggered: {agents}</span></div>"
        )


def _render_correlation() -> None:
    st.markdown("### 🔄 Multi-Dataset Correlation")
    inputs = " · ".join(CORRELATION_INPUTS)
    agents_html = "".join(
        f'<span class="corr-agent-pill">{icon} {name}</span>' for icon, name in CORRELATION_AGENTS
    )
    _card(
        f"""
        <div class="corr-visual">
            <div class="corr-inputs"><strong>Example inputs:</strong> {inputs}</div>
            <div style="font-size:1.1rem;color:#94a3b8;margin:0.4rem 0;">↓</div>
            <div class="corr-agents">{agents_html}</div>
            <div style="font-size:1.1rem;color:#94a3b8;margin:0.4rem 0;">↓</div>
            <div style="font-size:1rem;font-weight:800;color:#312e81;">🧠 Master RCA</div>
            <p style="color:#64748b;font-size:0.78rem;margin:0.5rem 0 0 0;">
                Different agents consume different datasets simultaneously.
                All findings are combined by the Master RCA agent.
            </p>
        </div>
        """
    )


def _render_activity_monitor(cell_id: str) -> None:
    st.markdown("### 🤖 Agent Activity Monitor")
    snap = _live_activity_snapshot(cell_id)
    active_keys = {str(a).lower() for a in snap["agents_run"]}

    metrics = f"""
    <div class="activity-grid">
        <div class="activity-metric"><div class="val" style="font-size:0.72rem;">{snap["dataset"]}</div><div class="lbl">Dataset</div></div>
        <div class="activity-metric"><div class="val">{len(snap["agents_run"])}</div><div class="lbl">Triggered agents</div></div>
        <div class="activity-metric"><div class="val">{snap["evidence_count"]}</div><div class="lbl">Evidence generated</div></div>
        <div class="activity-metric"><div class="val">{snap["confidence"]}%</div><div class="lbl">Confidence</div></div>
    </div>
    <p style="font-size:0.82rem;color:#334155;margin:0.4rem 0;">
        <strong>Last analysis ({cell_id}):</strong> {snap["primary_cause"][:140]}
    </p>
    """
    _card(metrics)

    monitor_agents = [
        (("ho_agent", "handover"), "Handover Agent"),
        (("transport_agent", "transport"), "Transport Agent"),
        (("gnb_syslog_agent", "gnb_syslog", "syslog"), "Syslog Agent"),
        (("rlf_agent", "rlf"), "RLF Agent"),
        (("vonr_agent", "vonr"), "VoNR Agent"),
        (("beamforming_agent", "beamforming", "beam"), "Beamforming Agent"),
    ]
    status_html = '<div class="agent-status-grid">'
    for aliases, label in monitor_agents:
        is_on = _agent_is_active(active_keys, *aliases)
        cls = "agent-on" if is_on else "agent-off"
        prefix = "✅" if is_on else "⚪"
        status_html += f'<div class="{cls}">{prefix} {label}</div>'
    status_html += "</div>"
    _card(status_html)
    if not snap.get("ok"):
        st.caption(f"Activity monitor using demo snapshot (live RCA: {snap.get('error', 'unavailable')})")


def _render_npi_center() -> None:
    st.markdown("### 🚀 NPI Validation Center")
    tags = "".join(f'<span class="npi-tag">✅ {item}</span>' for item in NPI_VALIDATION_ITEMS)
    _card(
        f"""
        <div class="npi-center">
            <strong>Purpose:</strong> Validate telecom network changes before and after deployment —
            software upgrades, feature activations, hardware swaps, and customer acceptance testing.
            <div class="npi-tags">{tags}</div>
        </div>
        """
    )


def _render_change_impact() -> None:
    st.markdown("### 📊 Change Impact Analysis")
    flow = [
        "Before Dataset", "+", "After Dataset", "→", "AI Comparison Engine", "→",
        "Agent Analysis", "→", "Regression Detection", "→", "Deployment Recommendation",
    ]
    flow_html = '<div class="impact-flow">'
    for item in flow:
        if item in ("+", "→"):
            flow_html += f'<span style="color:#94a3b8;">{item}</span>'
        else:
            flow_html += f'<span class="impact-step">{item}</span>'
    flow_html += "</div>"
    _card(
        f"""
        <div class="impact-box">
            {flow_html}
            <hr style="border:none;border-top:1px solid #e2e8f0;margin:0.8rem 0;"/>
            <strong>Example — Software upgrade 24R1 → 24R3</strong><br/>
            <span style="color:#166534;">✅ Throughput +14% &nbsp; ✅ VoNR setup success +2%</span><br/>
            <span style="color:#b45309;">⚠ HO prep failure +5%</span><br/>
            <strong>Risk:</strong> Medium &nbsp;·&nbsp;
            <strong>Recommendation:</strong> Proceed with limited rollout
        </div>
        """
    )


def _render_deployment_readiness() -> None:
    st.markdown("### ✅ Deployment Readiness Assessment")
    _card(
        """
        <p style="font-size:0.84rem;color:#475569;margin-bottom:0.6rem;">
            Outputs: <strong style="color:#16a34a;">PASS</strong> ·
            <strong style="color:#ca8a04;">PASS WITH RISKS</strong> ·
            <strong style="color:#dc2626;">FAIL</strong>
        </p>
        <div class="readiness-pass">
            <div class="readiness-title">PASS WITH RISKS</div>
            <p style="margin:0.4rem 0;font-size:0.84rem;color:#713f12;">
                <strong>Release:</strong> 24R3<br/>
                <span style="color:#166534;">✅ Throughput improved &nbsp; ✅ VoNR improved</span><br/>
                <span style="color:#b45309;">⚠ Mobility regression detected</span><br/>
                <strong>Confidence:</strong> 95%
            </p>
        </div>
        """
    )


def _render_deployment_roadmap() -> None:
    st.markdown("### 🌍 Real-World Deployment Roadmap")
    tiers = [
        ("t0", "🧪 Current PoC", "Synthetic datasets · CSV upload · multi-agent RCA · recommendations"),
        ("t1", "📱 Field Logs", "TEMS · Nemo · QXDM · UE log exports"),
        ("t2", "🏢 OSS / NetAct", "PM counters · alarm exports · syslog feeds"),
        ("t3", "🚀 Near Real-Time AI Operations", "Streaming PM · live syslogs · predictive analytics · auto RCA"),
    ]
    html = '<div class="deploy-timeline">'
    for i, (cls, title, detail) in enumerate(tiers):
        if i > 0:
            html += '<div style="text-align:center;color:#94a3b8;font-size:1.1rem;">↓</div>'
        html += f'<div class="deploy-tier {cls}"><strong>{title}</strong><br/>{detail}</div>'
    html += "</div>"
    _card(html)
    _card(
        """
        <p style="font-size:0.86rem;color:#1e3a5f;background:#eff6ff;border:1px solid #bfdbfe;
            border-radius:10px;padding:0.85rem 1rem;line-height:1.55;">
            <strong>Executive message:</strong> The current PoC validates AI orchestration, RCA logic,
            confidence scoring, and agent collaboration using synthetic telecom datasets.
            <strong>Future phases replace the data source, not the AI architecture.</strong>
        </p>
        """
    )


def _render_npi_value() -> None:
    st.markdown("### Key Value to NPI Engineers")
    trad = [
        "Manual KPI analysis",
        "Manual log analysis",
        "Manual before/after comparison",
        "Multiple disconnected tools",
    ]
    ai_steps = [
        "Upload data", "Automatic classification", "Specialist agents",
        "Evidence correlation", "Master RCA", "Deployment recommendation",
    ]
    trad_li = "".join(f"<li>{t}</li>" for t in trad)
    ai_flow = " → ".join(ai_steps)
    benefits = "".join(f"<li>✅ {b}</li>" for b in NPI_BENEFITS)
    _card(
        f"""
        <div class="value-compare">
            <div class="value-col">
                <h5>Traditional workflow</h5>
                <ul>{trad_li}</ul>
            </div>
            <div class="value-col ai">
                <h5>AI-powered workflow</h5>
                <p style="margin:0;font-size:0.78rem;color:#1d4ed8;font-weight:600;">{ai_flow}</p>
                <ul style="margin-top:0.5rem;">{benefits}</ul>
            </div>
        </div>
        <div class="vision-box">
            <strong>Final vision:</strong> TNIC evolves from a telecom RCA dashboard into an
            AI-assisted NPI Validation Copilot — analyzing synthetic datasets today and future
            UE logs, gNB logs, CM snapshots, PM counters, OSS exports, alarms, and real network
            telemetry tomorrow.
        </div>
        """
    )


def render_npi_copilot_section(focus_cell: str = "XYZ401") -> None:
    """Render the full NPI Validation Copilot platform section."""
    _inject_styles()
    st.divider()
    _card(
        """
        <div class="npi-hero">
            <h2>AI-Powered Telecom Engineering &amp; NPI Validation Copilot</h2>
            <p>
                TNIC evolves beyond RCA dashboards into an end-to-end platform for
                dataset ingestion, multi-agent analysis, change impact assessment,
                and deployment readiness validation.
            </p>
        </div>
        """
    )

    _render_synthetic_datasets()
    st.divider()
    _render_future_sources()
    st.divider()
    _render_ingestion_pipeline()
    st.divider()
    _render_trigger_engine()
    st.divider()
    _render_correlation()
    st.divider()
    _render_activity_monitor(focus_cell)
    st.divider()
    _render_npi_center()
    st.divider()
    _render_change_impact()
    st.divider()
    _render_deployment_readiness()
    st.divider()
    _render_deployment_roadmap()
    st.divider()
    _render_npi_value()

    st.caption(
        "NPI Copilot · Upload & Analyze: sidebar **Upload** · Live RCA: **RCA Report** · "
        "All specialist agents: **Assurance Hub**"
    )
