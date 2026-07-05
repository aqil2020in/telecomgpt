#!/usr/bin/env python3
"""Generate handover_events_enriched.csv from handover_events.csv."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from tnic.datasets.handover_enrichment import write_enriched_handover_csv


def main() -> None:
    out = write_enriched_handover_csv()
    print(f"Wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
