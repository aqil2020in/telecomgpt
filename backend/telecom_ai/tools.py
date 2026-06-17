"""Tool-use framework — callable tools for multi-agent orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    tool: str
    ok: bool
    output: Any = None
    error: str | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}
        self._specs: dict[str, ToolSpec] = {}
        self.current_agent: str | None = None

    def register(
        self,
        name: str,
        fn: Callable[..., Any],
        *,
        description: str,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        self._tools[name] = fn
        self._specs[name] = ToolSpec(
            name=name,
            description=description,
            parameters=parameters or {"type": "object", "properties": {}},
        )

    def list_specs(self) -> list[dict]:
        return [s.model_dump() for s in self._specs.values()]

    def run(self, name: str, **kwargs: Any) -> ToolResult:
        from .guardrails import tool_allowed

        if self.current_agent and not tool_allowed(self.current_agent, name):
            return ToolResult(
                tool=name,
                ok=False,
                error=f"Tool '{name}' not allowed for agent '{self.current_agent}'",
            )
        fn = self._tools.get(name)
        if not fn:
            return ToolResult(tool=name, ok=False, error=f"Unknown tool: {name}")
        try:
            out = fn(**kwargs)
            return ToolResult(tool=name, ok=True, output=out)
        except Exception as e:
            return ToolResult(tool=name, ok=False, error=str(e))

    def run_batch(self, calls: list[dict]) -> list[ToolResult]:
        results = []
        for call in calls:
            name = call.get("tool") or call.get("name")
            args = call.get("arguments") or call.get("args") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            results.append(self.run(name, **args))
        return results


def build_tool_registry(db: Any) -> ToolRegistry:
    """Register all TelecomGPT tools."""
    from analytics.csv_tools import csv_summary, detect_rf_columns, load_csv_path
    from analytics.log_tools import log_summary
    from rag.retrieve import retrieve_with_citations

    reg = ToolRegistry()

    reg.register(
        "lookup_glossary",
        lambda term: db.glossary_lookup(term) or "Not found",
        description="Look up a telecom glossary term (PRACH, PDCCH, etc.)",
        parameters={
            "type": "object",
            "properties": {"term": {"type": "string"}},
            "required": ["term"],
        },
    )
    reg.register(
        "lookup_device",
        lambda query: db.answer_device(query) or "No device match",
        description="Query device band/combo capabilities",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )
    reg.register(
        "lookup_ca_endc",
        lambda query: db.answer_ca_endc_nrdc(query) or "No CA/EN-DC match",
        description="Check CA, EN-DC, or NR-DC combinations",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )
    reg.register(
        "calc_phy",
        lambda query: db.answer_phy_math(query) or "Could not compute",
        description="NR-ARFCN, GSCN, or peak throughput calculations",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )
    reg.register(
        "lookup_bands",
        lambda query: db.answer_band_regulatory(query) or db.list_bands(),
        description="NR/LTE band plans and regulatory info",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )
    reg.register(
        "rag_search",
        lambda query, k=5: retrieve_with_citations(query, k=k),
        description="Search ShareTechnote/3GPP reference chunks (BM25 + vector)",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    )
    reg.register(
        "memory_search",
        lambda query, session_id="", k=5: _memory_search(query, session_id, k),
        description="Search vector memory for past context and facts",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "session_id": {"type": "string"},
                "k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    )
    reg.register(
        "csv_summary",
        lambda path: csv_summary(load_csv_path(path)),
        description="Summarize a local CSV file (drive test, KPI)",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    )
    reg.register(
        "detect_rf_columns",
        lambda path: detect_rf_columns(load_csv_path(path)),
        description="Detect RSRP/lat/lon/throughput columns in CSV",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    )
    reg.register(
        "analyze_log",
        lambda path: log_summary(Path(path).read_text(encoding="utf-8", errors="replace")),
        description="Parse UE/gNB log file for level counts and errors",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    )
    reg.register(
        "list_kaggle_csvs",
        lambda: _list_kaggle_csvs(),
        description="List downloaded Kaggle CSV files available locally",
        parameters={"type": "object", "properties": {}},
    )
    reg.register(
        "hybrid_search",
        lambda query, session_id="", k=5: _hybrid_search(query, session_id, k),
        description="Hybrid BM25 + vector + live ShareTechnote/sqimway/3GPP fetch + Tavily web search",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}, "session_id": {"type": "string"}, "k": {"type": "integer"}},
            "required": ["query"],
        },
    )
    reg.register(
        "web_search",
        lambda query: _web_search(query),
        description="Telecom web search (Tavily) biased to sharetechnote.com, sqimway.com, and 3gpp.org",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    )
    reg.register(
        "live_reference_fetch",
        lambda query: _live_reference_fetch(query),
        description="Live-fetch ShareTechnote, sqimway, or 3GPP page for query topic",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    )
    reg.register(
        "run_drive_test_rules",
        lambda path: _drive_test_rules(path),
        description="Run SLA rules on drive-test CSV",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    )
    reg.register(
        "evaluate_rf_kpis",
        lambda path: _evaluate_rf_kpis(path),
        description="Grade SS-RSRP/RSRQ/SINR/CQI/RSSI/BLER/RI vs 3GPP-referenced thresholds",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    )
    reg.register(
        "explain_link_budget",
        lambda query="": _explain_link_budget(query),
        description="Explain SINR vs RSRQ and compute DL link budget with worked example (TS 38.215 / Friis)",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": [],
        },
    )
    reg.register(
        "plot_rf_map",
        lambda path: _plot_rf_map(path),
        description="Build RF map GeoJSON + geo chart from CSV",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    )
    reg.register(
        "compare_devices",
        lambda query: _compare_devices(db, query),
        description="Compare two devices mentioned in query",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    )
    reg.register(
        "export_excel",
        lambda path: _export_excel(path),
        description="Export CSV summary to Excel workbook",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    )
    reg.register(
        "generate_presentation",
        lambda topic, content, session_id="default": _generate_ppt(topic, content, session_id),
        description="Generate a PowerPoint report (.pptx) from topic and content",
        parameters={
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "content": {"type": "string"},
                "session_id": {"type": "string"},
            },
            "required": ["topic", "content"],
        },
    )

    return reg


def _memory_search(query: str, session_id: str = "", k: int = 5) -> list[dict]:
    try:
        from memory.vector_store import VectorMemory

        mem = VectorMemory()
        return mem.search(query, k=k, session_id=session_id or None)
    except Exception:
        return []


def _list_kaggle_csvs() -> list[dict]:
    base = Path(__file__).resolve().parent.parent / "data" / "kaggle"
    out = []
    for p in base.rglob("*.csv"):
        if p.is_file():
            out.append({"path": str(p), "name": p.name})
    return out


def _generate_ppt(topic: str, content: str, session_id: str = "default") -> dict:
    from ppt.generator import generate_presentation

    return generate_presentation(topic=topic, content=content, session_id=session_id)


def _hybrid_search(query: str, session_id: str = "", k: int = 5, live: bool = False):
    from rag.hybrid_retrieve import hybrid_retrieve

    return hybrid_retrieve(query, k=k, session_id=session_id or None, live=live)


def _web_search(query: str):
    from rag.web_search import web_search_telecom

    return web_search_telecom(query)


def _live_reference_fetch(query: str):
    from rag.live_fetch import fetch_live_for_query

    context, cites = fetch_live_for_query(query, [])
    return {"context": context, "citations": cites, "ok": bool(context)}


def _drive_test_rules(path: str):
    from analytics.drive_test_rules import run_drive_test_rules

    return run_drive_test_rules(path)


def _evaluate_rf_kpis(path: str):
    from analytics.rf_kpi import evaluate_rf_kpis

    return evaluate_rf_kpis(path)


def _explain_link_budget(query: str = ""):
    from analytics.link_budget import explain_link_budget_dict

    return explain_link_budget_dict(query or "")


def _plot_rf_map(path: str):
    from analytics.rf_map import build_rf_map_artifacts

    return build_rf_map_artifacts(path)


def _compare_devices(db: Any, query: str) -> str:
    ql = query.lower()
    found = []
    for dev_id in db.devices:
        label = dev_id.replace("_", " ").replace("samsung", "s").replace("google", "")
        if dev_id.replace("_", " ") in ql or dev_id in ql or label in ql:
            found.append(dev_id)
    if len(found) < 2:
        for hint in ("s23", "s24", "s25", "iphone 16", "pixel"):
            if hint in ql:
                for dev_id in db.devices:
                    if hint.replace(" ", "") in dev_id.replace("_", ""):
                        if dev_id not in found:
                            found.append(dev_id)
    if len(found) < 2:
        return "Could not find two devices to compare. Try: 'Compare S23 vs S24'."
    lines = []
    for d in found[:2]:
        ans = db.answer_device(d.replace("_", " "))
        lines.append(f"**{d}**\n{ans[:800]}")
    return "\n\n---\n\n".join(lines)


def _export_excel(path: str):
    from analytics.csv_tools import csv_summary, load_csv_path
    from export.excel_report import export_csv_summary_excel

    return export_csv_summary_excel(path, csv_summary(load_csv_path(path)))
