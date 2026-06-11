"""Shared LangGraph state for TelecomGPT orchestration."""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

Intent = Literal[
    "device",
    "ca_endc",
    "phy_math",
    "band_glossary",
    "glossary",
    "band_regulatory",
    "llm",
]


class TelecomState(TypedDict):
    query: str
    intent: Intent | None
    answer: str | None
    context: str | None
    steps: Annotated[list[str], operator.add]
