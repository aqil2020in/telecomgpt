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
