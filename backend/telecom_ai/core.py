"""TelecomAI — LangGraph router over the TelecomDB knowledge layer.

Routing order (via LangGraph):
    1. Device capability        (device name/alias mentioned)
    2. CA / EN-DC / NR-DC       (aggregation & dual-connectivity)
    3. ARFCN / GSCN / throughput (PHY-layer math via 3GPP calculators)
    4. FCC / band / glossary    (band plans, terms, US spectrum)
    5. LLM fallback             (grounded with knowledge-base context)
"""

from __future__ import annotations

from .graph import build_graph, initial_state
from .loaders import TelecomDB


class TelecomAI:
    def __init__(self, db_path: str):
        self.db = TelecomDB(db_path)
        self.graph = build_graph(self.db)

    def run(self, query: str) -> str:
        return self.run_with_trace(query)["answer"]

    def run_with_trace(self, query: str) -> dict:
        result = self.graph.invoke(initial_state(query))
        return {
            "answer": result.get("answer") or "",
            "intent": result.get("intent"),
            "steps": result.get("steps") or [],
        }
