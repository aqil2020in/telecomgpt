"""Fetch and chunk HTML reference pages for RAG."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests

DEFAULT_HEADERS = {
    "User-Agent": "TelecomGPT-RAG/1.0 (educational; +https://github.com/aqil2020in/telecomgpt)",
}

# Curated ShareTechnote 5G pages + 3GPP overview (high-level only).
SEED_URLS = [
    "https://www.sharetechnote.com/html/5G/Handbook_5G_Index.html",
    "https://www.sharetechnote.com/html/5G/5G_PRACH.html",
    "https://www.sharetechnote.com/html/5G/5G_CSI_RS.html",
    "https://www.sharetechnote.com/html/5G/5G_CarrierAggregation.html",
    "https://www.sharetechnote.com/html/5G/5G_RACH.html",
    "https://www.sharetechnote.com/html/5G/5G_PDCCH.html",
    "https://www.sharetechnote.com/html/5G/5G_PDSCH.html",
    "https://www.sharetechnote.com/html/5G/5G_PUSCH.html",
    "https://www.sharetechnote.com/html/5G/5G_PUCCH.html",
    "https://www.sharetechnote.com/html/5G/5G_SSB.html",
    "https://www.sharetechnote.com/html/5G/5G_FrameStructure.html",
    "https://www.sharetechnote.com/html/5G/5G_Numerology.html",
    "https://www.sharetechnote.com/html/5G/5G_MIMO.html",
    "https://www.sharetechnote.com/html/5G/5G_BeamManagement.html",
    "https://www.sharetechnote.com/html/5G/5G_EN_DC.html",
    "https://www.sharetechnote.com/html/5G/5G_NetworkArchitecture.html",
    "https://www.sharetechnote.com/html/5G/5G_CallProcess_InitialAttach.html",
    "https://www.sharetechnote.com/html/5G/5G_UE_Capability.html",
    "https://www.sharetechnote.com/html/5G/5G_PowerClass.html",
    "https://www.sharetechnote.com/html/5G/5G_RadioProtocolStackArchitecture.html",
    "https://www.sharetechnote.com/html/RF_Handbook_Index.html",
    "https://www.sharetechnote.com/html/RF_Handbook_SNR.html",
    "https://www.sharetechnote.com/html/RF_Handbook_LinkBudget.html",
    "https://www.sharetechnote.com/html/RF_Handbook_RF_FrontEnd_RxChain_Tutorial.html",
    "https://www.sharetechnote.com/html/RF_Handbook_FriisTransmissionEquation.html",
    "https://www.sharetechnote.com/html/RF_Handbook_NoiseFigure.html",
    "https://www.sharetechnote.com/html/RF_Handbook_dB_dBm_dBc.html",
    "https://www.sharetechnote.com/html/RF_Handbook_RRH.html",
    "https://www.sharetechnote.com/html/RF_Handbook_Sensitivity.html",
    "https://www.sharetechnote.com/html/RF_Handbook_PIM.html",
    "https://www.sharetechnote.com/html/RF_Handbook_ACLR_ACPR.html",
    "https://www.sharetechnote.com/html/LTE/LTE_Overview.html",
    "https://www.3gpp.org/technologies/5g-system-overview",
]

CHUNK_SIZE = 900
CHUNK_OVERLAP = 120


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip = False
        if tag in ("p", "br", "li", "h1", "h2", "h3", "h4", "tr"):
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            text = data.strip()
            if text:
                self._chunks.append(text + " ")

    def text(self) -> str:
        raw = "".join(self._chunks)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def fetch_html(url: str, timeout: int = 30) -> str:
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text()


def extract_title(html: str, url: str) -> str:
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    path = urlparse(url).path
    return path.rsplit("/", 1)[-1].replace(".html", "").replace("_", " ")


def discover_sharetechnote_links(html: str, base_url: str) -> list[str]:
    links = set()
    for href in re.findall(r'href=["\']([^"\']+)["\']', html, re.I):
        if href.startswith("#") or href.startswith("mailto:"):
            continue
        full = urljoin(base_url, href)
        if "sharetechnote.com/html/5G/" in full and full.endswith(".html"):
            links.add(full.split("#")[0])
    return sorted(links)


def discover_rf_handbook_links(html: str, base_url: str) -> list[str]:
    links = set()
    for href in re.findall(r'href=["\']([^"\']+)["\']', html, re.I):
        if href.startswith("#") or href.startswith("mailto:"):
            continue
        full = urljoin(base_url, href)
        if not full.endswith(".html") or "sharetechnote.com/html/" not in full:
            continue
        if "RF_Handbook" in full or full.rsplit("/", 1)[-1].startswith("RF_"):
            links.add(full.split("#")[0])
    return sorted(links)


def chunk_text(text: str, *, url: str, title: str, source: str) -> list[dict]:
    text = text.strip()
    if not text:
        return []
    chunks: list[dict] = []
    start = 0
    idx = 0
    while start < len(text):
        end = min(len(text), start + CHUNK_SIZE)
        if end < len(text):
            break_at = text.rfind(". ", start, end)
            if break_at > start + CHUNK_SIZE // 2:
                end = break_at + 1
        body = text[start:end].strip()
        if body:
            chunks.append(
                {
                    "id": f"{source}:{idx}",
                    "source": source,
                    "url": url,
                    "title": title,
                    "text": body,
                }
            )
            idx += 1
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def ingest_urls(urls: Iterable[str], *, follow_index: bool = True) -> list[dict]:
    all_urls = list(dict.fromkeys(urls))
    if follow_index:
        extra_5g: list[str] = []
        extra_rf: list[str] = []
        for url in list(all_urls):
            try:
                if "Handbook_5G_Index" in url:
                    html = fetch_html(url)
                    extra_5g.extend(discover_sharetechnote_links(html, url))
                if "RF_Handbook_Index" in url:
                    html = fetch_html(url)
                    extra_rf.extend(discover_rf_handbook_links(html, url))
            except Exception:
                pass
        merged = list(dict.fromkeys([*all_urls, *extra_5g]))[:80]
        rf_add = [u for u in extra_rf if u not in merged][:40]
        all_urls = list(dict.fromkeys([*merged, *rf_add]))[:120]

    out: list[dict] = []
    seen_text: set[str] = set()
    for url in all_urls:
        try:
            html = fetch_html(url)
            text = html_to_text(html)
            if len(text) < 80:
                continue
            title = extract_title(html, url)
            source = urlparse(url).netloc.replace("www.", "")
            for ch in chunk_text(text, url=url, title=title, source=source):
                key = ch["text"][:200]
                if key in seen_text:
                    continue
                seen_text.add(key)
                out.append(ch)
        except Exception:
            continue
    return out
