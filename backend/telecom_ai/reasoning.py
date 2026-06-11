"""LLM fallback reasoning for queries the rule-based router cannot answer.

Providers (set ``TELECOMGPT_LLM``):

    ollama  — local Ollama OpenAI-compatible API (default http://localhost:11434/v1)
    openai  — OpenAI cloud API via ``OPENAI_API_KEY``
    auto    — try Ollama if reachable, else OpenAI if key set (default)

Ollama only works when the backend runs on the same machine as Ollama (or can
reach ``OLLAMA_BASE_URL``). A Render-deployed API cannot call your home PC
without a tunnel (ngrok, Cloudflare Tunnel, etc.).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from urllib.error import URLError
from urllib.request import urlopen

if TYPE_CHECKING:
    from .loaders import TelecomDB

_SYSTEM_PROMPT = (
    "You are TelecomGPT, an expert assistant for cellular/RF engineering "
    "(5G NR, LTE, 3GPP specifications). Answer concisely and precisely. "
    "Ground your answer in the provided knowledge-base context when relevant, "
    "and cite 3GPP spec clauses where applicable. If you are not sure, say so."
)

_OLLAMA_DEFAULT_BASE = "http://localhost:11434/v1"
_OLLAMA_DEFAULT_MODEL = "llama3.1:latest"
_OPENAI_DEFAULT_MODEL = "gpt-4o-mini"


def llm_answer(query: str, db: "TelecomDB") -> str:
    context = db.context_for(query)

    answer = _call_configured_llm(query, context)
    if answer:
        return answer

    # Deterministic offline fallback: PHY math, CA/EN-DC combos, glossary,
    # then band lookup.
    from .loaders import looks_like_phy_math

    if looks_like_phy_math(query):
        phy = db.answer_phy_math(query)
        if phy:
            return phy
    combo = db.answer_ca_endc_nrdc(query)
    if combo:
        return combo
    gloss = db.glossary_lookup(query)
    if gloss:
        return gloss
    band = db.answer_band_regulatory(query)
    if band:
        return band

    unknown = db.answer_unknown_query(query)
    if unknown:
        return unknown

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
        f"For open-ended Q&A locally: run Ollama and set TELECOMGPT_LLM=ollama, "
        f"or set OPENAI_API_KEY for cloud."
    )


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


def _call_configured_llm(query: str, context: str) -> str | None:
    provider = _llm_provider()

    if provider == "ollama":
        return _call_chat_api(
            query,
            context,
            base_url=_ollama_base_url(),
            api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
            model=os.environ.get("OLLAMA_MODEL", _OLLAMA_DEFAULT_MODEL),
        )

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return None
        return _call_chat_api(
            query,
            context,
            base_url=None,
            api_key=api_key,
            model=os.environ.get("TELECOMGPT_MODEL", _OPENAI_DEFAULT_MODEL),
        )

    # auto: prefer local Ollama when running on same host, else OpenAI
    if _ollama_reachable():
        answer = _call_chat_api(
            query,
            context,
            base_url=_ollama_base_url(),
            api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
            model=os.environ.get("OLLAMA_MODEL", _OLLAMA_DEFAULT_MODEL),
        )
        if answer:
            return answer

    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return _call_chat_api(
            query,
            context,
            base_url=None,
            api_key=api_key,
            model=os.environ.get("TELECOMGPT_MODEL", _OPENAI_DEFAULT_MODEL),
        )
    return None


def _call_chat_api(
    query: str,
    context: str,
    *,
    base_url: str | None,
    api_key: str,
    model: str,
) -> str | None:
    try:
        from openai import OpenAI
    except ImportError:
        return None

    user_content = query
    if context:
        user_content = f"Knowledge-base context:\n{context}\n\nQuestion: {query}"

    try:
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = OpenAI(**kwargs, timeout=float(os.environ.get("LLM_TIMEOUT_SEC", "120")))
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
            max_tokens=500,
        )
        content = response.choices[0].message.content
        return content.strip() if content else None
    except Exception:
        return None
