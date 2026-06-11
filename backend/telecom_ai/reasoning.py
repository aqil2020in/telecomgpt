"""LLM fallback reasoning for queries the rule-based router cannot answer.

If ``OPENAI_API_KEY`` is set (and the ``openai`` package is installed), the
query is sent to an LLM grounded with context assembled from the knowledge
base. Otherwise a deterministic fallback answers from the glossary or returns
guidance — the app stays fully functional offline.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .loaders import TelecomDB

_SYSTEM_PROMPT = (
    "You are TelecomGPT, an expert assistant for cellular/RF engineering "
    "(5G NR, LTE, 3GPP specifications). Answer concisely and precisely. "
    "Ground your answer in the provided knowledge-base context when relevant, "
    "and cite 3GPP spec clauses where applicable. If you are not sure, say so."
)


def llm_answer(query: str, db: "TelecomDB") -> str:
    context = db.context_for(query)

    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        answer = _call_openai(query, context, api_key)
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
        f"For open-ended Q&A, add OPENAI_API_KEY in Render → Environment and redeploy."
    )


def _call_openai(query: str, context: str, api_key: str) -> str | None:
    try:
        from openai import OpenAI
    except ImportError:
        return None

    try:
        client = OpenAI(api_key=api_key)
        user_content = query
        if context:
            user_content = f"Knowledge-base context:\n{context}\n\nQuestion: {query}"
        response = client.chat.completions.create(
            model=os.environ.get("TELECOMGPT_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
            max_tokens=500,
        )
        return response.choices[0].message.content
    except Exception:
        # Network/auth failures degrade gracefully to the offline fallback.
        return None
