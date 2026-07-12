#!/usr/bin/env python3
"""Generate manager PDF handout: TelecomGPT & TNIC RCA Dashboard implementation."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "TelecomGPT_TNIC_Implementation_Handout.pdf"


class HandoutPDF(FPDF):
    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "TelecomGPT & TNIC RCA Dashboard - Implementation Handout", align="C")
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")

    def cover(self) -> None:
        self.add_page()
        self.ln(30)
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(20, 60, 120)
        self.multi_cell(0, 12, "TelecomGPT & XYZ TNIC\nRCA Dashboard", align="C")
        self.ln(8)
        self.set_font("Helvetica", "", 14)
        self.set_text_color(60, 60, 60)
        self.multi_cell(0, 8, "Full Implementation Overview\nManager Handout", align="C")
        self.ln(20)
        self.set_font("Helvetica", "", 11)
        self.multi_cell(
            0,
            6,
            "Repository: github.com/aqil2020in/telecomgpt\n"
            "Products: TelecomGPT (chat AI) + XYZ TNIC (Network Intelligence Copilot)\n"
            "Demo cells: XYZ401-XYZ410 | Synthetic OSS-shaped datasets",
            align="C",
        )

    def section_title(self, title: str) -> None:
        self.ln(4)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(20, 60, 120)
        self.multi_cell(0, 8, title)
        self.set_draw_color(20, 60, 120)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def subsection(self, title: str) -> None:
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 6, title)
        self.ln(1)

    def body(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5, text)
        self.ln(1)

    def bullet(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        x = self.get_x()
        self.cell(6, 5, "-")
        self.multi_cell(0, 5, text)
        self.set_x(x)

    def table(self, headers: list[str], rows: list[list[str]], col_widths: list[int] | None = None) -> None:
        if col_widths is None:
            usable = self.w - self.l_margin - self.r_margin
            col_widths = [int(usable / len(headers))] * len(headers)
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(230, 240, 250)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 7, h, border=1, fill=True)
        self.ln()
        self.set_font("Helvetica", "", 8)
        for row in rows:
            max_h = 7
            for i, cell in enumerate(row):
                self.cell(col_widths[i], max_h, cell[:80], border=1)
            self.ln()


def build_pdf() -> Path:
    pdf = HandoutPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.cover()

    # Page 2 - Overview
    pdf.add_page()
    pdf.section_title("1. Executive Summary")
    pdf.body(
        "TelecomGPT is a domain-specific multi-agent AI platform for 5G/LTE RF and network "
        "operations. The monorepo contains two related products plus shared analytics tooling. "
        "The XYZ TNIC (Telecom Network Intelligence Copilot) RCA Dashboard is a Streamlit "
        "multipage application that visualizes network health and runs explainable, rule-based "
        "root cause analysis across 17 domain pages."
    )
    pdf.subsection("Products in the monorepo")
    pdf.table(
        ["Product", "Location", "Purpose"],
        [
            ["TelecomGPT Chat", "backend/ + frontend/", "LangGraph chat + embedded RCA"],
            ["XYZ TNIC", "xyz_tnic/", "Standalone RCA API + Streamlit dashboard"],
            ["Analytics", "analytics/", "Generic CSV/log charts (optional)"],
        ],
        [45, 45, 100],
    )
    pdf.ln(2)
    pdf.subsection("Production deployment")
    pdf.bullet("Chat UI: Vercel (telecomgpt.vercel.app)")
    pdf.bullet("API: Render (telecomgpt.onrender.com)")
    pdf.bullet("TNIC Dashboard: Streamlit local/Docker demo (port 8502)")

    pdf.section_title("2. Architecture")
    pdf.body(
        "The same RCA engine exists in two places: xyz_tnic/tnic/ (standalone, full product) "
        "and backend/tnic/ (embedded in TelecomGPT chat via bridge.py). Both share agents, "
        "rules, datasets, and the Master RCA Orchestrator."
    )
    pdf.subsection("Data flow (preloaded demo path)")
    pdf.bullet("CSV files on disk: /workspace/datasets/*.csv (15 synthetic files)")
    pdf.bullet("registry.py resolves dataset directory (TNIC_DATASETS_DIR env override)")
    pdf.bullet("loaders.py reads CSVs with @lru_cache (one read per Streamlit process)")
    pdf.bullet("kpi_service.py merges all sources into compute_cell_kpis(cell_id)")
    pdf.bullet("dashboard_utils.py exposes cell_kpis(), domain DataFrames, run_agent()")
    pdf.bullet("dashboard/pages/*.py renders metrics, charts, and agent findings")

    # Page 3 - Dashboard
    pdf.add_page()
    pdf.section_title("3. How the RCA Dashboard Was Built")
    pdf.subsection("Technology")
    pdf.body(
        "Built with Streamlit multipage convention. Entry point: xyz_tnic/dashboard/app.py. "
        "Each file in dashboard/pages/ becomes a sidebar page automatically. Numeric prefixes "
        "(2_, 3_, ...) control sort order. No custom router required."
    )
    pdf.subsection("Home page (app.py) sections")
    pdf.table(
        ["Section", "Module", "Purpose"],
        [
            ["Executive KPIs", "app.py", "Cluster health, worst cells, charts"],
            ["Data Sources", "data_sources_section.py", "Page to CSV mapping table"],
            ["AI RCA Workflow", "rca_workflow_section.py", "Multi-agent workflow explainer"],
            ["NPI Copilot", "npi_copilot_section.py", "NPI validation + agent monitor"],
            ["Dataset Simulation", "dataset_simulation_section.py", "Upload/simulate RCA"],
        ],
        [40, 55, 95],
    )
    pdf.ln(2)
    pdf.subsection("Sidebar navigation")
    pdf.body(
        "Global Focus cell selectbox (XYZ401-XYZ410) in sidebar. Streamlit auto-discovers "
        "17 domain pages plus home. Shared logic lives in dashboard_utils.py."
    )

    pdf.section_title("4. Standard Page Pattern")
    pdf.body("Every domain page (Handover, RLF, VoNR, etc.) follows the same 3-layer pattern:")
    pdf.bullet("Layer 1 - Metrics: cell_kpis(cell_id) from merged KPI service")
    pdf.bullet("Layer 2 - Visualization: domain DataFrame filtered by cell (charts + tables)")
    pdf.bullet("Layer 3 - RCA: run_agent(domain, cell_id) returns rule engine findings")
    pdf.ln(1)
    pdf.body(
        "Exceptions: RCA Report runs full MasterRCAOrchestrator; Assurance Hub runs all 12 "
        "agents; Upload uses ingest pipeline; RF Coverage uses geospatial Plotly maps."
    )

    # Page 4 - Sidebar pages
    pdf.add_page()
    pdf.section_title("5. Sidebar Pages Inventory")
    pages = [
        ("Handover", "handover_events_enriched.csv", "HOAgent"),
        ("RLF", "rlf_events.csv", "RLFAgent"),
        ("Call Drops", "call_drop_events.csv", "CallDropAgent"),
        ("RACH", "rach_events.csv + PM", "RACHAgent"),
        ("Throughput", "throughput_metrics.csv", "ThroughputAgent"),
        ("Beamforming", "PM + synthetic beams", "BeamformingAgent"),
        ("VoNR", "vonr_sessions.csv", "VoNRAgent"),
        ("ANR", "anr_events.csv", "ANRAgent"),
        ("Config Audit", "cell_configuration.csv", "ConfigAuditAgent"),
        ("gNB Syslog", "gnb_syslog.csv", "GNBSyslogAgent"),
        ("Alarm Correlation", "alarm_events.csv", "AlarmAgent"),
        ("UE Protocol", "ue_protocol_trace.csv", "UEProtocolAgent"),
        ("RF Coverage", "geospatial RF CSV", "RFCoverageAgent"),
        ("RCA Report", "All merged KPIs", "MasterRCAOrchestrator"),
        ("Assurance Hub", "All assurance CSVs", "All 12 agents"),
        ("Upload", "User files", "Dynamic RCA pipeline"),
    ]
    pdf.table(["Page", "Data Source", "Agent"], pages, [42, 68, 80])

    pdf.ln(3)
    pdf.section_title("6. RCA Agent Pipeline")
    pdf.subsection("Specialist agents (12+)")
    pdf.body(
        "File: xyz_tnic/tnic/agents/specialists.py. Each agent wraps a deterministic rule "
        "engine (tnic/rules/*.py). Returns rule_id, probable_cause, confidence, evidence, "
        "and recommended_actions. No LLM required for core RCA."
    )
    pdf.subsection("Master RCA Orchestrator")
    pdf.body("File: xyz_tnic/tnic/orchestrator/rca_orchestrator.py. Steps:")
    pdf.bullet("1. detect_issue_type() - keyword classifier")
    pdf.bullet("2. ORCHESTRATION_MAP selects 8-12 specialist agents")
    pdf.bullet("3. Fan-out: each agent runs analyze(kpis, query)")
    pdf.bullet("4. Primary rule engine pass + call-drop classifier")
    pdf.bullet("5. master_rca.py enrichment (coverage correlation, workflows)")
    pdf.bullet("6. rank_findings() with domain boost (+10%) and classifier boost (+15%)")
    pdf.bullet("7. Output: ranked causes, actions, health score, knowledge graph")
    pdf.body("28 NOC-grade workflows defined in rca_catalog.py (coverage hole, ping-pong, VoNR drop, etc.)")

    # Page 5 - Integration & decisions
    pdf.add_page()
    pdf.section_title("7. TelecomGPT Integration")
    pdf.body(
        "File: backend/tnic/bridge.py. When users ask RCA-style questions in the Next.js chat, "
        "looks_like_tnic_rca_query() detects intent, run_tnic_rca() loads KPIs from datasets, "
        "runs MasterRCAOrchestrator, and returns markdown plus agent trace. Same engine, "
        "different UI (chat vs Streamlit)."
    )

    pdf.section_title("8. Upload & Dynamic RCA Path")
    pdf.bullet("User uploads file via Upload page or home simulation")
    pdf.bullet("file_classifier.py identifies format (CSV, log, Excel, zip)")
    pdf.bullet("normalization_engine.py maps to canonical event schema")
    pdf.bullet("Stored as events.jsonl under xyz_tnic/data/uploads/<id>/")
    pdf.bullet("dynamic_rca.py merges upload KPIs with bundled cell KPIs")
    pdf.bullet("MasterRCAOrchestrator produces full RCA report")
    pdf.body("Upload is additive - does not replace preloaded CSVs for sidebar pages.")

    pdf.section_title("9. Key Design Decisions")
    pdf.bullet("CSV-first demo with OSS-shaped schema - swap data via loaders, not orchestration")
    pdf.bullet("Rule-based RCA core, OpenAI optional for narrative reports only")
    pdf.bullet("Single KPI merge layer (kpi_service.py) - no hard-coded UI numbers")
    pdf.bullet("Consistent page template - metrics + charts + agent findings")
    pdf.bullet("Two products, one engine - standalone TNIC + TelecomGPT embed")
    pdf.bullet("Assurance datasets first-class - VoNR, ANR, syslog, alarms, UE trace")

    pdf.section_title("10. How to Run & Demo")
    pdf.body("From repo root:")
    pdf.set_font("Courier", "", 9)
    pdf.multi_cell(0, 5, "cd xyz_tnic\nexport TNIC_DATASETS_DIR=/workspace/datasets\nstreamlit run dashboard/app.py --server.port 8502")
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.body("Recommended demo flow for management:")
    pdf.set_font("Helvetica", "", 10)
    pdf.bullet("1. Home - cluster health, data sources, RCA workflow explainer")
    pdf.bullet("2. Handover - pick XYZ401, show KPIs + HO Agent findings")
    pdf.bullet("3. VoNR or RLF - domain-specific RCA")
    pdf.bullet("4. RCA Report - full multi-agent orchestration")
    pdf.bullet("5. Assurance Hub - all 12 agents on one cell")
    pdf.bullet("6. Upload/Simulation - live ingest to Master RCA")

    pdf.section_title("11. Documentation References")
    pdf.table(
        ["Document", "Path"],
        [
            ["Full architecture", "docs/ARCHITECTURE.md"],
            ["Dashboard data flow", "docs/TNIC_DASHBOARD_DATA_FLOW.md"],
            ["Handover RCA deep dive", "docs/RCA_AGENT_END_TO_END_HANDOVER.md"],
            ["Manager demo script", "docs/DEMO_MANAGER.md"],
            ["Platform overview PDF", "docs/XYZ Telecom TNIC.pdf"],
            ["Cloud agent commands", "AGENTS.md"],
        ],
        [55, 135],
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUTPUT))
    return OUTPUT


if __name__ == "__main__":
    path = build_pdf()
    print(f"Generated: {path} ({path.stat().st_size:,} bytes)")
