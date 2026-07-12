#!/usr/bin/env python3
"""Generate manager PDF: RCA Dashboard explainer (layman speaker script)."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "RCA_MANAGER_EXPLAINER.pdf"


class ExplainerPDF(FPDF):
    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "RCA Dashboard - Manager Explainer", align="C")
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")

    def cover(self) -> None:
        self.add_page()
        self.ln(28)
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(20, 60, 120)
        self.multi_cell(0, 12, "RCA Dashboard\nManager Explainer", align="C")
        self.ln(8)
        self.set_font("Helvetica", "", 13)
        self.set_text_color(60, 60, 60)
        self.multi_cell(0, 7, "How RCA Agents Work - Step by Step\nPlain-language speaker script", align="C")
        self.ln(18)
        self.set_font("Helvetica", "", 10)
        self.multi_cell(
            0, 6,
            "Demo cells: XYZ401-XYZ410\n"
            "Repo: github.com/aqil2020in/telecomgpt\n"
            "Companion: docs/RCA_MANAGER_EXPLAINER.md",
            align="C",
        )

    def section(self, title: str) -> None:
        self.ln(3)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(20, 60, 120)
        self.multi_cell(0, 7, title)
        self.ln(2)

    def body(self, text: str) -> None:
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5, text)
        self.ln(1)

    def bullet(self, text: str) -> None:
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.cell(6, 5, "-")
        self.multi_cell(0, 5, text)

    def say_box(self, text: str) -> None:
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "I", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 5, f'Say: "{text}"')
        self.ln(2)
        self.set_text_color(30, 30, 30)

    def step(self, label: str, desc: str) -> None:
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5, f"{label}: {desc}")
        self.ln(1)


def build_pdf() -> Path:
    pdf = ExplainerPDF()
    pdf.set_auto_page_break(auto=True, margin=14)

    pdf.cover()
    pdf.add_page()

    pdf.section("1. Opening (30 seconds)")
    pdf.say_box(
        "Our RCA dashboard is like a network doctor. We already loaded sample network data "
        "for 10 demo cells. When I pick a cell, the system reads that data, calculates health "
        "numbers, runs expert checks, and tells us the most likely root cause and what to fix - "
        "with evidence, not guesswork."
    )

    pdf.section("2. Five layers (draw on whiteboard)")
    pdf.bullet("Layer 1 - DATASETS (CSV): Raw events already in GitHub datasets/ folder")
    pdf.bullet("Layer 2 - KPI SERVICE: Calculator - turns events into rates (87% HO success)")
    pdf.bullet("Layer 3 - RULES: Telecom checklists (if metric > threshold, flag issue)")
    pdf.bullet("Layer 4 - RCA AGENTS: Expert doctors (Handover, RLF, VoNR, Alarm...)")
    pdf.bullet("Layer 5 - DASHBOARD: What you see - charts, findings, final report")
    pdf.body("Data flows UP: CSV -> KPIs -> Rules -> Agents -> Screen")

    pdf.section("3. Preloaded data - what to tell manager")
    pdf.body("We did NOT type data into the dashboard for each cell.")
    pdf.bullet("15 CSV files in GitHub: telecomgpt/datasets/")
    pdf.bullet("Each row tagged with cell ID (XYZ401, XYZ402, ...)")
    pdf.bullet("Your only input: pick a cell from the dropdown")
    pdf.say_box(
        "Preloaded means demo data is shipped with the product. We only select the cell; "
        "the events are already there."
    )

    pdf.add_page()
    pdf.section("4. Example A - Handover page (easiest demo)")
    pdf.body("Show: Sidebar -> Handover -> Cell XYZ401")
    pdf.ln(1)

    steps_a = [
        ("Step 1", "2_Handover.py opens the Handover screen."),
        ("Step 2", "dashboard_utils.py gets data for XYZ401."),
        ("Step 3", "loaders.py reads handover_events_enriched.csv from disk."),
        ("Step 4", "kpi_service.py calculates HO success %, prep fail %, Xn fail %."),
        ("Step 5", "Top of page = summary numbers. Middle = charts and event table (proof)."),
        ("Step 6", "HOAgent (specialists.py) runs ho_rules.py checklist on those KPIs."),
        ("Step 7", "Bottom = findings: cause, confidence, evidence, recommended actions."),
    ]
    for label, desc in steps_a:
        pdf.step(label, desc)
    pdf.ln(2)
    pdf.say_box(
        "Handover page is one dataset, one specialist, one checklist - one clear diagnosis for mobility."
    )

    pdf.section("5. Example B - RCA Report (full team demo)")
    pdf.body("Show: RCA Report -> XYZ401 -> Handover failure -> Run Master RCA")
    pdf.ln(1)

    steps_b = [
        ("Step 1", "8_RCA_Report.py - you ask: why is handover failing on XYZ401?"),
        ("Step 2", "kpi_service.py merges ALL CSVs into one health profile for the cell."),
        ("Step 3", "rca_orchestrator.py calls many agents: HO, RLF, Alarm, Transport, ANR..."),
        ("Step 4", "Each agent runs its rules/*.py checklist on the same KPI summary."),
        ("Step 5", "master_rca.py links related issues; orchestrator ranks findings."),
        ("Step 6", "health_scoring.py gives overall score (e.g. 52/100)."),
        ("Step 7", "Screen shows: root cause, evidence, recommendations, confidence %."),
    ]
    for label, desc in steps_b:
        pdf.step(label, desc)
    pdf.ln(2)
    pdf.say_box(
        "RCA Report is all datasets, all specialists, team lead ranking - "
        "the final engineering answer with evidence and fix steps."
    )

    pdf.add_page()
    pdf.section("6. How it works WITHOUT Render")
    pdf.body(
        "The Streamlit RCA dashboard does NOT need telecomgpt.onrender.com for demos. "
        "One Python process on your machine = dashboard + RCA engine together."
    )
    pdf.bullet("Step 1: streamlit run dashboard/app.py")
    pdf.bullet("Step 2: loaders.py reads CSV from datasets/ (disk, no network)")
    pdf.bullet("Step 3: kpi_service.py calculates rates per cell")
    pdf.bullet("Step 4: Pages show charts (proof) + metrics (summary)")
    pdf.bullet("Step 5: agents + rules/*.py run local IF/THEN checklists")
    pdf.bullet("Step 6: Findings on screen - no Render, no OpenAI required")
    pdf.ln(1)
    pdf.say_box(
        "Dashboard demo runs on this machine like Excel plus macros - "
        "Render is a separate door for chat and API, not needed for this demo."
    )
    pdf.body("Two paths, same RCA brain:")
    pdf.bullet("Dashboard: Your PC -> Streamlit -> CSV -> Rules -> Screen (NO Render)")
    pdf.bullet("Chat/API: Browser -> Vercel -> Render -> TNIC rules (uses Render)")
    pdf.body("Upload page ONLY can optionally call Render API; all sidebar pages stay local.")

    pdf.section("6b. What runs where - HOW and WHERE")
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(230, 240, 250)
    w = [38, 42, 110]
    for i, h in enumerate(["Thing", "Where", "How"]):
        pdf.cell(w[i], 6, h, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 7)
    wr_rows = [
        ("Streamlit UI", "Your machine", "streamlit run dashboard/app.py - one Python process"),
        ("CSV data", "Disk datasets/", "loaders.py pd.read_csv - preloaded files"),
        ("KPI calculation", "Your machine", "kpi_service.py counts rows, computes rates"),
        ("RCA agents/rules", "Your machine", "specialists.py + rules/*.py IF/THEN checks"),
        ("Handover/RLF/RCA", "Your machine", "pages/*.py -> utils -> agents -> screen"),
    ]
    for r in wr_rows:
        pdf.set_x(pdf.l_margin)
        pdf.cell(w[0], 6, r[0], border=1)
        pdf.cell(w[1], 6, r[1], border=1)
        pdf.cell(w[2], 6, r[2][:95], border=1)
        pdf.ln()
    pdf.ln(2)
    pdf.body("Handover trace: Browser -> 2_Handover.py -> loaders -> kpi_service -> HOAgent -> findings")
    pdf.body("NOT on your machine for demo: Render API, live OSS. OpenAI optional only.")
    pdf.body("Machines involved: 1. Cloud services: 0.")
    pdf.ln(1)
    pdf.body("ARCHITECTURE diagram shows PRODUCTION (Render has RCA + data for chat).")
    pdf.body("Local Streamlit demo (Mode B) uses same code/CSVs on YOUR machine - both true.")

    pdf.add_page()
    pdf.section("7. Handover vs RCA Report")
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 240, 250)
    cols = [45, 70, 75]
    for i, h in enumerate(["", "Handover page", "RCA Report"]):
        pdf.cell(cols[i], 6, h, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    rows = [
        ("Question", "How is HO?", "Why is HO failing?"),
        ("Data", "Mainly HO CSV", "All CSVs merged"),
        ("Experts", "1 Handover Agent", "8-12 agents"),
        ("Output", "Few findings", "Ranked root cause + report"),
    ]
    for r in rows:
        pdf.set_x(pdf.l_margin)
        pdf.cell(cols[0], 6, r[0], border=1)
        pdf.cell(cols[1], 6, r[1], border=1)
        pdf.cell(cols[2], 6, r[2], border=1)
        pdf.ln()

    pdf.ln(3)
    pdf.section("8. Key Python files (if asked)")
    pdf.bullet("Page UI: dashboard/pages/2_Handover.py or 8_RCA_Report.py")
    pdf.bullet("Glue: dashboard/dashboard_utils.py")
    pdf.bullet("Read CSV: datasets/loaders.py")
    pdf.bullet("Calculate rates: datasets/kpi_service.py")
    pdf.bullet("Experts: agents/specialists.py")
    pdf.bullet("Checklists: rules/ho_rules.py, rlf_rules.py, ...")
    pdf.bullet("Team lead: orchestrator/rca_orchestrator.py")

    pdf.section("9. Manager FAQ - quick answers")
    faq = [
        ("Did we enter data manually?", "No - preloaded CSV files in GitHub datasets/."),
        ("Uses Render backend?", "No for dashboard demo - local Streamlit + CSV + Python."),
        ("Is it AI / ChatGPT?", "Core is rule-based. AI optional for summary text only."),
        ("OpenAI cost?", "$0 unless narrative report ON + API key set."),
        ("Can we trust it?", "Every finding shows evidence and rule ID - auditable."),
        ("Real network later?", "Replace CSVs with real OSS exports; same agents/rules."),
        ("Business value?", "Faster RCA, one view across mobility/RF/voice/alarms."),
    ]
    for q, a in faq:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 9)
        pdf.multi_cell(0, 5, f"Q: {q}")
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, f"A: {a}")
        pdf.ln(1)

    pdf.section("10. Five-minute demo script")
    demo = [
        "0-1 min: Home - show 10 cells XYZ401-410",
        "1-2 min: Handover XYZ401 - metrics + charts",
        "2-3 min: Scroll to HO Agent findings",
        "3-4 min: RCA Report - Run Master RCA",
        "4-5 min: Point at root cause, evidence, recommendations, confidence",
    ]
    for d in demo:
        pdf.bullet(d)

    pdf.ln(2)
    pdf.section("11. One sentence to memorize")
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "I", 10)
    pdf.multi_cell(
        0, 5,
        "We preload demo network data in CSV files; when you pick a cell, the system summarizes "
        "it into KPIs, runs telecom expert rules through RCA agents, and delivers a ranked root "
        "cause with evidence, confidence, and fix steps - Handover shows one expert; "
        "RCA Report shows the full team.",
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUTPUT))
    return OUTPUT


if __name__ == "__main__":
    path = build_pdf()
    print(f"Generated: {path} ({path.stat().st_size:,} bytes)")
