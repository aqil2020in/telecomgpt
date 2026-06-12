"""NR band catalog loader (sqimway / TS 38.104)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_CATALOG = Path(__file__).resolve().parent.parent / "data" / "nr_bands_catalog.json"
_BAND_RE = re.compile(r"^n(\d{1,3})$", re.I)


def load_nr_bands_catalog() -> dict[str, Any]:
    if not _CATALOG.exists():
        return {"bands": {}, "count": 0}
    return json.loads(_CATALOG.read_text(encoding="utf-8"))


def get_nr_band(band_id: str) -> dict[str, Any] | None:
    bid = band_id.strip().lower()
    if not bid.startswith("n"):
        bid = f"n{bid}"
    catalog = load_nr_bands_catalog()
    return catalog.get("bands", {}).get(bid)


def list_nr_bands(*, fr: str | None = None) -> dict[str, dict[str, Any]]:
    catalog = load_nr_bands_catalog()
    bands = catalog.get("bands", {})
    if not fr:
        return bands
    frl = fr.upper()
    return {
        bid: info
        for bid, info in bands.items()
        if str(info.get("frequency_range", "")).upper().startswith(frl)
    }


def search_nr_bands(query: str, *, limit: int = 20) -> list[dict[str, Any]]:
    ql = query.lower().strip()
    catalog = load_nr_bands_catalog()
    hits: list[tuple[int, str, dict[str, Any]]] = []

    for bid, info in catalog.get("bands", {}).items():
        score = 0
        if ql == bid or ql == bid[1:]:
            score = 100
        elif bid in ql:
            score = 50
        blob = json.dumps(info, default=str).lower()
        for token in ql.replace("+", " ").split():
            if len(token) >= 2 and token in blob:
                score += 5
        if info.get("common_name", "").lower() in ql:
            score += 10
        if score:
            hits.append((score, bid, info))

    hits.sort(key=lambda x: (-x[0], int(x[1][1:])))
    return [{"band": bid, **info} for _, bid, info in hits[:limit]]
