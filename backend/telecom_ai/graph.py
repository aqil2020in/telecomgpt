"""LangGraph workflow — orchestrates existing TelecomDB handlers as graph nodes."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .loaders import TelecomDB, looks_like_phy_math
from .reasoning import llm_answer
from .state import Intent, TelecomState

_DEVICE_KW = ("s23", "s24", "s25", "iphone 16", "iphone 17", "pixel")
_CA_KW = ("ca", "carrier aggregation", "endc", "nrdc")
_DEFINE_KW = ("what is", "what's", "explain", "define", "describe", "tell me about")


def build_graph(db: TelecomDB):
    graph = StateGraph(TelecomState)

    def classify(state: TelecomState) -> dict:
        q = state["query"].lower()
        query = state["query"]
        intent: Intent = "llm"

        if any(k in q for k in _DEVICE_KW):
            intent = "device"
        elif any(k in q for k in _CA_KW):
            intent = "ca_endc"
        elif looks_like_phy_math(query):
            intent = "phy_math"
        elif any(p in q for p in _DEFINE_KW):
            intent = "band_glossary"
        elif db.glossary_lookup(query):
            intent = "glossary"
        elif any(k in q for k in ("fcc", "us band", "nr band")):
            intent = "band_regulatory"

        return {
            "intent": intent,
            "context": db.context_for(query),
            "steps": [f"classify -> {intent}"],
        }

    def device_node(state: TelecomState) -> dict:
        answer = db.answer_device(state["query"]) or None
        return {"answer": answer, "steps": ["node:device"]}

    def ca_node(state: TelecomState) -> dict:
        answer = db.answer_ca_endc_nrdc(state["query"]) or None
        return {"answer": answer, "steps": ["node:ca_endc"]}

    def phy_node(state: TelecomState) -> dict:
        answer = db.answer_phy_math(state["query"]) or None
        return {"answer": answer, "steps": ["node:phy_math"]}

    def band_glossary_node(state: TelecomState) -> dict:
        answer = db.answer_band_regulatory(state["query"])
        if not answer:
            answer = db.glossary_lookup(state["query"])
        return {"answer": answer or None, "steps": ["node:band_glossary"]}

    def glossary_node(state: TelecomState) -> dict:
        answer = db.glossary_lookup(state["query"]) or None
        return {"answer": answer, "steps": ["node:glossary"]}

    def band_regulatory_node(state: TelecomState) -> dict:
        answer = db.answer_band_regulatory(state["query"]) or None
        return {"answer": answer, "steps": ["node:band_regulatory"]}

    def llm_node(state: TelecomState) -> dict:
        answer = llm_answer(state["query"], db)
        return {"answer": answer, "steps": ["node:llm"]}

    graph.add_node("classify", classify)
    graph.add_node("device", device_node)
    graph.add_node("ca_endc", ca_node)
    graph.add_node("phy_math", phy_node)
    graph.add_node("band_glossary", band_glossary_node)
    graph.add_node("glossary", glossary_node)
    graph.add_node("band_regulatory", band_regulatory_node)
    graph.add_node("llm", llm_node)

    graph.add_edge(START, "classify")

    graph.add_conditional_edges(
        "classify",
        lambda s: s["intent"] or "llm",
        {
            "device": "device",
            "ca_endc": "ca_endc",
            "phy_math": "phy_math",
            "band_glossary": "band_glossary",
            "glossary": "glossary",
            "band_regulatory": "band_regulatory",
            "llm": "llm",
        },
    )

    def after_handler(state: TelecomState) -> str:
        if state.get("answer"):
            return END
        return "llm"

    for node in (
        "device",
        "ca_endc",
        "phy_math",
        "band_glossary",
        "glossary",
        "band_regulatory",
    ):
        graph.add_conditional_edges(node, after_handler, {END: END, "llm": "llm"})

    graph.add_edge("llm", END)

    return graph.compile()


def initial_state(query: str) -> TelecomState:
    return {
        "query": query,
        "intent": None,
        "answer": None,
        "context": None,
        "steps": [],
    }
