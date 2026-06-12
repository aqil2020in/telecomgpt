"""Live fetch — ShareTechnote, sqimway, and 3GPP pages to supplement static RAG."""

from __future__ import annotations

import os
import re
from typing import Any

from .ingest import extract_title, fetch_html, html_to_text

_SHARETECH = re.compile(r"sharetechnote\.com", re.I)
_3GPP = re.compile(r"3gpp\.org", re.I)
_SQIMWAY = re.compile(r"sqimway\.com", re.I)
_TOPIC_RE = re.compile(r"\b(prach|rach|pdcch|pdsch|pusch|pucch|ssb|numerology|mimo|beam|endc|nr)\b", re.I)
_BAND_RE = re.compile(r"\bn(\d{1,3})\b", re.I)
_TS_RE = re.compile(r"\b(?:ts\s*)?(\d{2})[\s.-](\d{3})(?:-\d+)?\b", re.I)

SQIMWAY_NR_BAND_URL = "https://www.sqimway.com/nr_band.php"
SQIMWAY_LTE_BAND_URL = "https://www.sqimway.com/lte_band.php"

_3GPP_5G_OVERVIEW = "https://www.3gpp.org/technologies/5g-system-overview"
_3GPP_LTE_OVERVIEW = "https://www.3gpp.org/technologies/lte-advanced-pro"

_3GPP_SERIES_URL = {
    "21": "https://www.3gpp.org/dynareport/21-series.htm",
    "22": "https://www.3gpp.org/dynareport/22-series.htm",
    "23": "https://www.3gpp.org/dynareport/23-series.htm",
    "24": "https://www.3gpp.org/dynareport/24-series.htm",
    "28": "https://www.3gpp.org/dynareport/28-series.htm",
    "29": "https://www.3gpp.org/dynareport/29-series.htm",
    "33": "https://www.3gpp.org/dynareport/33-series.htm",
    "36": "https://www.3gpp.org/dynareport/36-series.htm",
    "37": "https://www.3gpp.org/dynareport/37-series.htm",
    "38": "https://www.3gpp.org/dynareport/38-series.htm",
}

# Common spec → series shortcut for tighter live excerpts
_TS_LAYER_HINTS = {
    "38.104": "NR base station RF / band plans",
    "38.331": "NR RRC protocol",
    "38.306": "NR UE radio access capabilities",
    "38.321": "NR MAC",
    "38.322": "NR RLC",
    "38.323": "NR PDCP",
    "38.300": "NR overall description (Stage-2)",
    "38.211": "NR physical channels and modulation",
    "24.501": "5GS NAS protocol",
    "23.501": "5G System architecture",
    "36.331": "LTE RRC",
}


def guess_sharetechnote_url(query: str) -> str | None:
    """Guess a ShareTechnote 5G page from query terms."""
    ql = query.lower()
    slug_map = {
        "prach": "PRACH",
        "rach": "RACH",
        "pdcch": "PDCCH",
        "pdsch": "PDSCH",
        "pusch": "PUSCH",
        "pucch": "PUCCH",
        "ssb": "SSB",
        "numerology": "Numerology",
        "mimo": "MIMO",
        "beam management": "BeamManagement",
        "beam": "BeamManagement",
        "en-dc": "EN_DC",
        "endc": "EN_DC",
        "frame structure": "FrameStructure",
        "framestructure": "FrameStructure",
        "protocol stack": "RadioProtocolStackArchitecture",
        "initial attach": "CallProcess_InitialAttach",
        "ue capability": "UE_Capability",
        "power class": "PowerClass",
    }
    for term, slug in slug_map.items():
        if term in ql:
            return f"https://www.sharetechnote.com/html/5G/5G_{slug}.html"
    m = _TOPIC_RE.search(query)
    if m:
        slug = m.group(1).upper()
        if slug == "BEAM":
            return "https://www.sharetechnote.com/html/5G/5G_BeamManagement.html"
        if slug == "NR":
            return "https://www.sharetechnote.com/html/5G/Handbook_5G_Index.html"
        return f"https://www.sharetechnote.com/html/5G/5G_{slug}.html"
    return None


def extract_band_ids(query: str) -> list[str]:
    return sorted({f"n{m.group(1)}" for m in _BAND_RE.finditer(query)}, key=lambda b: int(b[1:]))


def extract_ts_specs(query: str) -> list[str]:
    specs: list[str] = []
    for m in _TS_RE.finditer(query):
        spec = f"{m.group(1)}.{m.group(2)}"
        if spec not in specs:
            specs.append(spec)
    return specs


def guess_sqimway_targets(query: str) -> list[tuple[str, str | None]]:
    """Return (kind, band_id) targets — kind is 'band' or 'page'."""
    ql = query.lower()
    targets: list[tuple[str, str | None]] = []
    bands = extract_band_ids(query)
    band_kw = (
        "band plan", "nr band", "frequency band", "duplex", "arfcn", "channel bandwidth",
        "38.104", "sqimway", "downlink", "uplink mhz", "tdd", "fdd",
    )
    if bands or any(k in ql for k in band_kw):
        if bands:
            for bid in bands[:2]:
                targets.append(("band", bid))
        else:
            targets.append(("page", None))
    if "lte band" in ql or "e-utra band" in ql:
        targets.append(("lte_page", None))
    return targets


def guess_3gpp_urls(query: str) -> list[str]:
    ql = query.lower()
    urls: list[str] = []
    specs = extract_ts_specs(query)
    for spec in specs[:3]:
        series = spec.split(".")[0]
        url = _3GPP_SERIES_URL.get(series)
        if url and url not in urls:
            urls.append(url)
    if not urls and any(k in ql for k in ("3gpp", "ts ", "specification", "spec clause")):
        if any(k in ql for k in ("lte", "36.", "e-utra", "4g")):
            urls.append(_3GPP_LTE_OVERVIEW)
        else:
            urls.append(_3GPP_5G_OVERVIEW)
            if "38." in ql or "nr" in ql or "5g" in ql:
                urls.append(_3GPP_SERIES_URL["38"])
            if "23." in ql or "24." in ql or "5gc" in ql or "core" in ql:
                for s in ("23", "24"):
                    u = _3GPP_SERIES_URL[s]
                    if u not in urls:
                        urls.append(u)
    return urls


def extract_ts_rows_from_html(html: str, ts_spec: str) -> str:
    """Pull matching TS rows from a 3GPP dynareport series page."""
    text = html_to_text(html)
    needles = (f"TS {ts_spec}", f"TS {ts_spec.replace('.', '-')}")
    lines = [ln.strip() for ln in text.splitlines() if any(n in ln for n in needles)]
    if not lines:
        return ""
    hint = _TS_LAYER_HINTS.get(ts_spec, "")
    header = f"3GPP TS {ts_spec}" + (f" — {hint}" if hint else "")
    return header + "\n" + "\n".join(lines[:6])


def fetch_page_excerpt(url: str, *, max_chars: int = 3500) -> dict[str, Any]:
    """Fetch and return live page text excerpt."""
    html = fetch_html(url, timeout=12)
    text = html_to_text(html)
    title = extract_title(html, url)
    if not text.strip():
        return {"ok": False, "url": url, "error": "empty page"}
    provider = "sharetechnote"
    if _3GPP.search(url):
        provider = "3gpp"
    elif _SQIMWAY.search(url):
        provider = "sqimway"
    return {
        "ok": True,
        "url": url,
        "title": title,
        "text": text[:max_chars],
        "live": True,
        "source": "live_fetch",
        "provider": provider,
    }


def fetch_3gpp_live(query: str, url: str) -> dict[str, Any] | None:
    specs = extract_ts_specs(query)
    try:
        html = fetch_html(url, timeout=12)
    except Exception:
        return None
    if specs and "dynareport" in url:
        parts = [extract_ts_rows_from_html(html, spec) for spec in specs[:2]]
        body = "\n\n".join(p for p in parts if p)
        if body:
            return {
                "ok": True,
                "url": url,
                "title": f"3GPP TS {', '.join(specs[:2])} (live series lookup)",
                "text": body[:3500],
                "live": True,
                "source": "live_fetch",
                "provider": "3gpp",
            }
    page = fetch_page_excerpt(url)
    return page if page.get("ok") else None


def fetch_sqimway_band(band_id: str) -> dict[str, Any] | None:
    try:
        from analytics.nr_bands import live_sqimway_band_excerpt

        result = live_sqimway_band_excerpt(band_id)
        if not result:
            return None
        text, cite = result
        return {
            "ok": True,
            "url": cite["url"],
            "title": cite["title"],
            "text": text,
            "live": cite.get("live", True),
            "source": cite.get("source", "live_fetch"),
            "provider": "sqimway",
        }
    except Exception:
        return None


def _live_fetch_max() -> int:
    try:
        return max(1, min(4, int(os.environ.get("TELECOMGPT_LIVE_FETCH_MAX", "2"))))
    except ValueError:
        return 2


def _allowed_live_url(url: str) -> bool:
    return bool(_SHARETECH.search(url) or _3GPP.search(url) or _SQIMWAY.search(url))


def fetch_live_for_query(query: str, rag_cites: list[dict] | None = None) -> tuple[str, list[dict]]:
    """Fetch live content from ShareTechnote, sqimway, 3GPP, and top RAG URLs."""
    parts: list[str] = []
    cites: list[dict] = []
    seen_urls: set[str] = set()
    max_fetches = _live_fetch_max()

    def _add_page(page: dict[str, Any]) -> bool:
        url = page.get("url") or ""
        if not url or url in seen_urls or not page.get("ok"):
            return False
        seen_urls.add(url)
        label = page.get("provider") or "live"
        parts.append(f"Live [{label}]: {page['title']} ({url})\n{page['text']}")
        cites.append(
            {
                "title": page["title"],
                "url": url,
                "source": page.get("source", "live_fetch"),
                "live": page.get("live", True),
                "provider": page.get("provider"),
            }
        )
        return True

    # 1) sqimway band rows (live TS 38.104 tables)
    for kind, band_id in guess_sqimway_targets(query):
        if len(cites) >= max_fetches:
            break
        if kind == "band" and band_id:
            page = fetch_sqimway_band(band_id)
            if page:
                _add_page(page)
        elif kind in ("page", "lte_page"):
            url = SQIMWAY_LTE_BAND_URL if kind == "lte_page" else SQIMWAY_NR_BAND_URL
            if url not in seen_urls:
                try:
                    _add_page(fetch_page_excerpt(url))
                except Exception:
                    pass

    # 2) 3GPP series / overview pages
    for url in guess_3gpp_urls(query):
        if len(cites) >= max_fetches:
            break
        if url in seen_urls:
            continue
        page = fetch_3gpp_live(query, url)
        if page:
            _add_page(page)

    # 3) ShareTechnote topic guess
    guess_st = guess_sharetechnote_url(query)
    if guess_st and guess_st not in seen_urls and len(cites) < max_fetches:
        try:
            _add_page(fetch_page_excerpt(guess_st))
        except Exception:
            pass

    # 4) Top static RAG cite URLs on allowed domains
    for c in rag_cites or []:
        if len(cites) >= max_fetches:
            break
        u = c.get("url") or ""
        if not u or u in seen_urls or not _allowed_live_url(u):
            continue
        try:
            if _3GPP.search(u):
                page = fetch_3gpp_live(query, u)
            else:
                page = fetch_page_excerpt(u)
            if page:
                _add_page(page)
        except Exception:
            continue

    return "\n\n---\n\n".join(parts), cites
