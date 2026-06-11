"""TelecomAI — keyword router over the TelecomDB knowledge layer.

Routing order:
    1. Device capability        (device name/alias mentioned)
    2. CA / EN-DC / NR-DC       (aggregation & dual-connectivity)
    3. ARFCN / GSCN / throughput (PHY-layer math via 3GPP calculators)
    4. FCC / band regulatory    (band plans, US spectrum)
    5. LLM fallback             (grounded with knowledge-base context)
"""

from __future__ import annotations

from .loaders import TelecomDB, looks_like_phy_math
from .reasoning import llm_answer


class TelecomAI:
    def __init__(self, db_path: str):
        self.db = TelecomDB(db_path)

    def run(self, query: str) -> str:
        q = query.lower()

        # 1. Device capability
        if any(k in q for k in ["s23", "s24", "s25", "iphone 16", "iphone 17", "pixel"]):
            resp = self.db.answer_device(query)
            if resp:
                return resp

        # 2. CA / EN-DC / NR-DC
        if "ca" in q or "carrier aggregation" in q or "endc" in q or "nrdc" in q:
            resp = self.db.answer_ca_endc_nrdc(query)
            if resp:
                return resp

        # 3. ARFCN / GSCN / throughput (keyword or calculable pattern)
        if looks_like_phy_math(query):
            resp = self.db.answer_phy_math(query)
            if resp:
                return resp

        # 4. FCC / bands / glossary ("what is n78?", "what is 5G?")
        if "what is" in q or "what's" in q:
            resp = self.db.answer_band_regulatory(query)
            if resp:
                return resp
            resp = self.db.glossary_lookup(query)
            if resp:
                return resp

        if "fcc" in q or "us band" in q or "nr band" in q:
            resp = self.db.answer_band_regulatory(query)
            if resp:
                return resp

        # 5. Fallback: LLM reasoning with context
        return llm_answer(query, self.db)
