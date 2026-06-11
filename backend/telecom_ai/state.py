"""Shared LangGraph state for TelecomGPT orchestration."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

Intent = Literal[
    "device",
    "ca_endc",
    "phy_math",
    "band_glossary",
    "glossary",
    "band_regulatory",
    "llm",
]


class TelecomState(TypedDict, total=False):
    query: str
    intent: Intent | None
    answer: str | None
    context: str | None
    history: list[dict[str, str]]
    sources: list[dict]
    steps: Annotated[list[str], operator.add]

ChatMessage = dict[str, Any]
