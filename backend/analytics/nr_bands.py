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


def format_band_excerpt(band_id: str, info: dict[str, Any]) -> str:
    """Human-readable band summary for RAG / live fetch."""
    lines = [f"**{band_id.upper()}** — {info.get('common_name') or 'NR band'} (TS 38.104)"]
    if info.get("duplex"):
        lines.append(f"- Duplex: {info['duplex']} · Range: {info.get('frequency_range', '—')}")
    if info.get("downlink_mhz"):
        lo, hi = info["downlink_mhz"]
        lines.append(f"- DL: {lo}–{hi} MHz")
    if info.get("uplink_mhz"):
        lo, hi = info["uplink_mhz"]
        lines.append(f"- UL: {lo}–{hi} MHz")
    if info.get("channel_bandwidth_mhz"):
        bws = info["channel_bandwidth_mhz"]
        lines.append(f"- Channel BW: {', '.join(str(b) for b in bws[:12])} MHz")
    if info.get("scs_khz"):
        lines.append(f"- SCS: {', '.join(str(s) for s in info['scs_khz'])} kHz")
    if info.get("geographical_area"):
        lines.append(f"- Region: {info['geographical_area']}")
    if info.get("spec_release"):
        lines.append(f"- 3GPP release: {info['spec_release']}")
    if info.get("note"):
        lines.append(f"- Note: {info['note']}")
    if info.get("notes"):
        lines.append(f"- Notes: {info['notes']}")
    return "\n".join(lines)


def live_sqimway_band_excerpt(band_id: str) -> tuple[str, dict[str, Any]] | None:
    """Live sqimway fetch with local catalog fallback."""
    import importlib.util

    bid = band_id.strip().lower()
    if not bid.startswith("n"):
        bid = f"n{bid}"

    source_url = "https://www.sqimway.com/nr_band.php"
    live: dict[str, Any] | None = None
    try:
        mod_path = _CATALOG.resolve().parent.parent / "scripts" / "import_nr_bands_sqimway.py"
        spec = importlib.util.spec_from_file_location("_sqimway_import", mod_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            source_url = mod.SOURCE_URL
            live = mod.fetch_live_band(bid)
    except Exception:
        live = None

    if live:
        text = format_band_excerpt(bid, live)
        return text, {
            "title": f"{bid.upper()} — sqimway NR band (live)",
            "url": source_url,
            "source": "live_fetch",
            "live": True,
            "provider": "sqimway",
        }
    cached = get_nr_band(bid)
    if cached:
        text = format_band_excerpt(bid, cached)
        return text, {
            "title": f"{bid.upper()} — NR band (local catalog)",
            "url": source_url,
            "source": "catalog",
            "live": False,
            "provider": "sqimway",
        }
    return None
