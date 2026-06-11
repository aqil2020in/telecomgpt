"""TelecomGPT — domain-specific AI engine for cellular/RF engineering questions.

Exposes :class:`TelecomAI`, a keyword router over the :class:`TelecomDB`
knowledge layer, with an optional LLM fallback for open-ended questions.
"""

from .core import TelecomAI
from .loaders import TelecomDB

__all__ = ["TelecomAI", "TelecomDB"]
__version__ = "0.2.0"
