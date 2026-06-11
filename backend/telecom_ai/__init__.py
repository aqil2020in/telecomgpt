"""TelecomGPT — domain-specific AI engine for cellular/RF engineering questions.

Exposes :class:`TelecomAI`, a keyword router over the :class:`TelecomDB`
knowledge layer, with an optional LLM fallback for open-ended questions.
"""

from .core import TelecomAI
from .graph import build_graph
from .loaders import TelecomDB

__all__ = ["TelecomAI", "TelecomDB", "build_graph"]
__version__ = "0.2.0"
