"""LLM fallback with RAG over ShareTechnote / 3GPP reference chunks."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from urllib.error import URLError
from urllib.request import urlopen

if TYPE_CHECKING:
    from .loaders import TelecomDB

try:
    from rag.retrieve import retrieve_with_citations
except ImportError:
    retrieve_with_citations = None  # type: ignore

_SYSTEM_PROMPT = (
    "You are TelecomGPT, an expert assistant for cellular/RF engineering "
    "(5G NR, LTE, 3GPP specifications). Give clear, structured, detailed answers "
    "like a technical blog post: use headings or bullet points when helpful, "
    "compare technologies side-by-side when asked, and cite 3GPP spec clauses "
    "where applicable. Use the knowledge-base and reference excerpts provided; "
    "when reference excerpts are included, synthesize them and mention source URLs. "
    "Always end with a 'Sources' section listing ShareTechnote/3GPP/web URLs used. "
    "Prefer provided excerpts over general knowledge; if excerpts conflict with memory, trust excerpts. "
    "If you are not sure, say so."
)

_OLLAMA_DEFAULT_BASE = "http://localhost:11434/v1"
_OLLAMA_DEFAULT_MODEL = "llama3.1:latest"
_OPENAI_DEFAULT_MODEL = "gpt-4o-mini"


def llm_answer(
    query: str,
    db: "TelecomDB",
    history: list[dict[str, str]] | None = None,
) -> str:
    answer, _ = llm_answer_with_sources(query, db, history=history)
    return answer


def llm_answer_with_sources(
    query: str,
    db: "TelecomDB",
    history: list[dict[str, str]] | None = None,
    extra_context: str | None = None,
    *,
    fast: bool = False,
) -> tuple[str, list[dict]]:
    kb_context = db.context_for(query)
    rag_context, cites = _retrieve(query, fast=fast)

    comparison = db.answer_comparison(query)

    merged = _merge_context(kb_context, rag_context)
    if comparison:
        merged = f"Built-in comparison summary:\n{comparison}\n\n{merged}".strip()
    if extra_context:
        merged = f"Multi-agent research outputs:\n{extra_context}\n\n{merged}".strip()

    answer = _call_configured_llm(query, merged, history=history, fast=fast)
    if answer:
        return _append_sources(answer, cites), cites

    meta = db.answer_meta(query)
    if meta:
        return meta, cites

    rag_only = _rag_only_answer(query, cites, rag_context)
    if rag_only:
        return rag_only, cites

    if comparison:
        return comparison, cites

    from .loaders import looks_like_phy_math

    if looks_like_phy_math(query):
        phy = db.answer_phy_math(query)
        if phy:
            return phy, cites
    combo = db.answer_ca_endc_nrdc(query)
    if combo:
        return combo, cites
    gloss = db.glossary_lookup(query)
    if gloss:
        return gloss, cites
    band = db.answer_band_regulatory(query)
    if band:
        return band, cites

    unknown = db.answer_unknown_query(query)
    if unknown:
        return unknown, cites

    handbook = db.db.get("glossary_refs", {}).get(
        "handbook",
        "https://www.sharetechnote.com/html/5G/Handbook_5G_Index.html",
    )
    samples = ", ".join(sorted(db.db.get("glossary", {}))[:10])

    return (
        f"I couldn't map that to a telecom intent.\n\n"
        f"Known topics: {samples}, NR bands (n78), devices (S24), CA/EN-DC, "
        f"ARFCN/GSCN math.\n\n"
        f"5G handbook: {handbook}\n\n"
        f"Run `python backend/scripts/ingest_rag.py` to refresh reference chunks."
    ), cites


def _retrieve(query: str, *, fast: bool = False) -> tuple[str, list[dict]]:
    k = 3 if fast else int(os.environ.get("RAG_TOP_K", "5"))
    if fast:
        if retrieve_with_citations is None:
            return "", []
        return retrieve_with_citations(query, k=k)
    try:
        from rag.hybrid_retrieve import hybrid_retrieve

        return hybrid_retrieve(query, k=k)
    except Exception:
        pass
    if retrieve_with_citations is None:
        return "", []
    return retrieve_with_citations(query, k=k)


def _merge_context(kb: str, rag: str) -> str:
    parts = []
    if kb:
        parts.append(f"TelecomGPT knowledge base:\n{kb}")
    if rag:
        parts.append(f"Reference excerpts (ShareTechnote / 3GPP):\n{rag}")
    return "\n\n".join(parts)


def _append_sources(answer: str, cites: list[dict]) -> str:
    if not cites:
        return answer
    lines = [f"- {c.get('title', 'Source')}: {c.get('url', '')}" for c in cites[:5]]
    return answer + "\n\nSources:\n" + "\n".join(lines)


def _rag_only_answer(query: str, cites: list[dict], rag_context: str) -> str:
    if not rag_context:
        return ""
    from .loaders import _is_meta_query

    if _is_meta_query(query):
        return ""
    header = (
        "I couldn't reach the LLM on this server, so here is reference material instead. "
        "For full conversational answers, set OPENAI_API_KEY on Render (or run Ollama locally).\n\n"
    )
    return header + rag_context[:4000]


def _llm_provider() -> str:
    return os.environ.get("TELECOMGPT_LLM", "auto").strip().lower()


def _ollama_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", _OLLAMA_DEFAULT_BASE).rstrip("/")


def _ollama_reachable() -> bool:
    base = _ollama_base_url().removesuffix("/v1")
    try:
        with urlopen(f"{base}/api/tags", timeout=1.5) as resp:
            return resp.status == 200
    except (URLError, OSError, TimeoutError, ValueError):
        return False


def _call_configured_llm(
    query: str,
    context: str,
    history: list[dict[str, str]] | None = None,
    *,
    fast: bool = False,
) -> str | None:
    provider = _llm_provider()
    timeout = float(
        os.environ.get(
            "LLM_TIMEOUT_FAST_SEC" if fast else "LLM_TIMEOUT_SEC",
            "30" if fast else "120",
        )
    )

    if provider == "ollama":
        return _call_chat_api(
            query,
            context,
            history=history,
            base_url=_ollama_base_url(),
            api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
            model=os.environ.get("OLLAMA_MODEL", _OLLAMA_DEFAULT_MODEL),
            timeout=timeout,
        )

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return None
        return _call_chat_api(
            query,
            context,
            history=history,
            base_url=None,
            api_key=api_key,
            model=os.environ.get("TELECOMGPT_MODEL", _OPENAI_DEFAULT_MODEL),
            timeout=timeout,
        )

    if not fast and _ollama_reachable():
        answer = _call_chat_api(
            query,
            context,
            history=history,
            base_url=_ollama_base_url(),
            api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
            model=os.environ.get("OLLAMA_MODEL", _OLLAMA_DEFAULT_MODEL),
            timeout=timeout,
        )
        if answer:
            return answer

    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return _call_chat_api(
            query,
            context,
            history=history,
            base_url=None,
            api_key=api_key,
            model=os.environ.get("TELECOMGPT_MODEL", _OPENAI_DEFAULT_MODEL),
            timeout=timeout,
        )
    return None


def _call_chat_api(
    query: str,
    context: str,
    *,
    history: list[dict[str, str]] | None = None,
    base_url: str | None,
    api_key: str,
    model: str,
    timeout: float | None = None,
) -> str | None:
    try:
        from openai import OpenAI
    except ImportError:
        return None

    user_content = query
    if context:
        user_content = f"{context}\n\nQuestion: {query}"

    messages: list[dict[str, str]] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    for msg in (history or [])[-10:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_content})

    try:
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = OpenAI(
            **kwargs,
            timeout=timeout if timeout is not None else float(os.environ.get("LLM_TIMEOUT_SEC", "120")),
        )
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "1200")),
        )
        content = response.choices[0].message.content
        return content.strip() if content else None
    except Exception:
        return None


def call_llm_json(prompt: str) -> dict | None:
    """Call LLM and parse JSON object from response."""
    import json
    import re

    answer = _call_configured_llm(prompt, "", history=None)
    if not answer:
        return None
    match = re.search(r"\{.*\}", answer, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
