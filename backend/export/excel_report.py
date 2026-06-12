"""Excel export for analytics summaries."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "reports"


def export_csv_summary_excel(path: str, summary: dict, *, title: str = "TelecomGPT Report") -> dict:
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        return {"ok": False, "error": "openpyxl not installed. pip install openpyxl"}

    _OUTPUT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"telecomgpt_report_{ts}.xlsx"
    out = _OUTPUT / filename

    df = pd.read_csv(path)
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.head(500).to_excel(writer, sheet_name="Data", index=False)
        meta = pd.DataFrame([{"metric": k, "value": str(v)} for k, v in (summary or {}).items()])
        meta.to_excel(writer, sheet_name="Summary", index=False)

    return {"ok": True, "filename": filename, "download_url": f"/api/reports/{filename}", "type": "excel"}
