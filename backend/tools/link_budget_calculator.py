"""NR link budget + SINR vs RSRQ CLI. Run: python backend/tools/link_budget_calculator.py [query]"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.link_budget import explain_sinr_vs_rsrq_link_budget


def main() -> None:
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Explain SINR vs RSRQ link budget"
    print(explain_sinr_vs_rsrq_link_budget(query))


if __name__ == "__main__":
    main()
