"""TelecomDB — the knowledge layer of TelecomGPT.

Everything lives in one ``self.db`` dict:

    devices     — id -> path map (e.g. ``devices/samsung_s23.json``) or inline sheets
    arfcn_bands — per-band NR-ARFCN raster parameters
    gscn        — synchronization raster ranges (FR1/FR2)
    throughput_prb — PRB counts per bandwidth / SCS
    nr_bands / lte_bands — band plans
    ca_fr1 / ca_fr2 / ca_fr12 — network-level NR CA combos (combo -> note)
    endc_fr1 / endc_fr2 / endc_fr12 — EN-DC combos (combo -> note)
    nrdc        — NR-DC combos (combo -> note)
    fcc         — {licensed, unlicensed, mmwave} band lists
    glossary    — term definitions

Combos use ``+`` separators (e.g. ``n41+n71``, ``b66+n77+n261``); queries with
``-``/``_``/``/`` separators are normalized before matching.

Every ``answer_*`` method returns a formatted string, or ``""`` (falsy) so the
TelecomAI router can fall through to the next handler.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# Make backend/tools importable as a sibling package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.arfcn_calculator import arfcn_to_freq, freq_to_arfcn
from tools.gscn_calculator import gscn_to_freq, freq_to_gscn
from tools.throughput_calculator import nr_throughput

_SCS_TO_MU = {15: 0, 30: 1, 60: 2, 120: 3}
_OVERHEAD = {"dl": 0.14, "ul": 0.08}

_BAND_RE = re.compile(r"\b(n\d{1,3})\b", re.IGNORECASE)
_LTE_BAND_RE = re.compile(r"\b[bB](\d{1,2})\b")
_ARFCN_RE = re.compile(r"\barfcn\s*(?:=|:)?\s*(\d{3,7})", re.IGNORECASE)
_GSCN_RE = re.compile(r"\bgscn\s*(?:=|:)?\s*(\d{2,6})", re.IGNORECASE)
_FREQ_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(ghz|mhz)", re.IGNORECASE)
_BW_RE = re.compile(r"(\d+)\s*mhz", re.IGNORECASE)
_LAYERS_RE = re.compile(r"(\d)\s*(?:x\d\s*mimo|layers?|streams?)", re.IGNORECASE)
_QAM_RE = re.compile(r"(64|256|1024)\s*-?\s*qam", re.IGNORECASE)
_SCS_RE = re.compile(r"(15|30|60|120)\s*khz", re.IGNORECASE)

_COMBO_SECTIONS = ["ca_fr1", "ca_fr2", "ca_fr12", "endc_fr1", "endc_fr2", "endc_fr12", "nrdc"]

_SECTION_LABELS = {
    "ca_fr1": "FR1 carrier aggregation",
    "ca_fr2": "FR2 (mmWave) carrier aggregation",
    "ca_fr12": "FR1+FR2 carrier aggregation",
    "endc_fr1": "EN-DC (LTE anchor + FR1 NR)",
    "endc_fr2": "EN-DC (LTE anchor + FR2 NR)",
    "endc_fr12": "EN-DC (LTE anchor + FR1 and FR2 NR)",
    "nrdc": "NR-DC dual connectivity",
}

# Band combos in normalized text, e.g. "n41+n71" or "b66+n77+n261".
_COMBO_RE = re.compile(r"\b[bn]\d{1,3}(?:\+[bn]\d{1,3}){1,2}\b")

_DEVICE_COMBO_KINDS = (("ca", "NR carrier aggregation"),
                       ("endc", "EN-DC"),
                       ("nrdc", "NR-DC"))


def _normalize_combo_text(text: str) -> str:
    """Lowercase and unify -/_///+ separators (with optional surrounding
    whitespace) to a bare '+', keeping word boundaries intact so combos like
    'n41 - n71' or 'b66/n77' normalize to 'n41+n71' / 'b66+n77'."""
    return re.sub(r"\s*[-_/+]\s*", "+", text.lower())


def looks_like_phy_math(query: str) -> bool:
    """True when the query is likely an ARFCN/GSCN/throughput calculation."""
    ql = query.lower().strip()
    if any(k in ql for k in (
        "arfcn", "gscn", "throughput", "capacity", "prb",
        "data rate", "peak rate", "phy math", "phy layer",
    )):
        return True
    if _ARFCN_RE.search(query) or _GSCN_RE.search(query):
        return True
    if _BW_RE.search(query) and (_LAYERS_RE.search(query) or _QAM_RE.search(query)):
        return True
    if re.fullmatch(r"\d{2,7}", ql):
        return True
    if _FREQ_RE.search(query) and any(k in ql for k in ("arfcn", "convert", "frequency", "mhz to")):
        return True
    return False


class TelecomDB:
    def __init__(self, db_path: str):
        """``db_path`` may be the data directory or the master JSON file itself.

        Devices are loaded from ``self.db["devices"]`` when it is a path map
        (``"samsung_s23": "devices/samsung_s23.json"``), otherwise from inline
        objects or by globbing the adjacent ``devices/`` folder.
        """
        path = Path(db_path)
        if path.is_dir():
            master = path / "telecom_master_db.json"
        else:
            master = path

        with open(master, encoding="utf-8") as f:
            self.db: dict[str, Any] = json.load(f)
        self.db["devices"] = self._load_devices(master)

    def _load_devices(self, master: Path) -> dict[str, dict[str, Any]]:
        spec = self.db.get("devices", {})
        loaded: dict[str, dict[str, Any]] = {}

        if spec and isinstance(next(iter(spec.values()), None), str):
            for dev_id, rel_path in spec.items():
                with open(master.parent / rel_path, encoding="utf-8") as f:
                    loaded[dev_id] = json.load(f)
        elif spec and isinstance(next(iter(spec.values()), None), dict):
            loaded = spec

        if not loaded:
            devices_dir = master.parent / "devices"
            if devices_dir.is_dir():
                for file in sorted(devices_dir.glob("*.json")):
                    with open(file, encoding="utf-8") as f:
                        loaded[file.stem] = json.load(f)
        return loaded

    @property
    def devices(self) -> dict[str, dict[str, Any]]:
        return self.db["devices"]

    def _prb_from_db(self, bandwidth_mhz: int, scs_khz: int) -> int | None:
        row = self.db.get("throughput_prb", {}).get(f"{bandwidth_mhz}mhz")
        if row:
            return row.get(f"{scs_khz}khz")
        return None

    def _guess_arfcn_band(self, arfcn: int) -> str | None:
        bands = self.db.get("arfcn_bands", {})
        if not bands:
            return None
        return min(bands, key=lambda b: abs(arfcn - bands[b]["n_off_dl"]))

    def _arfcn_band_params(self, band: str) -> dict[str, Any] | None:
        return self.db.get("arfcn_bands", {}).get(band.lower())

    def _arfcn_band_freq(self, band: str, arfcn: int) -> str | None:
        params = self._arfcn_band_params(band)
        if not params:
            return None
        freq = arfcn_to_freq(arfcn, params)
        return (
            f"NR-ARFCN {arfcn} on {band}: {freq:.3f} MHz "
            f"(band raster, N_offs={params['n_off_dl']}, "
            f"F_offs={params['f_off_dl']} MHz, step={params['step']} MHz)."
        )

    def _freq_to_arfcn_band(self, band: str, freq_mhz: float) -> str | None:
        params = self._arfcn_band_params(band)
        if not params:
            return None
        arfcn = freq_to_arfcn(freq_mhz, params)
        exact = arfcn_to_freq(arfcn, params)
        return (
            f"{freq_mhz:.3f} MHz on {band} maps to NR-ARFCN {arfcn} "
            f"(exact center {exact:.3f} MHz, band raster, step={params['step']} MHz)."
        )

    def _gscn_fr_label(self, gscn: int) -> str | None:
        cfg = self.db.get("gscn", {})
        for key in ("fr1", "fr2"):
            r = cfg.get(key, {})
            if r.get("min", -1) <= gscn <= r.get("max", 10**9):
                return key
        return None

    def _gscn_fr_for_freq(self, freq_mhz: float) -> str | None:
        cfg = self.db.get("gscn", {})
        if not cfg:
            return None
        # Prefer the raster whose simplified inverse lands in range.
        for key in ("fr2", "fr1"):
            gscn = freq_to_gscn(freq_mhz, key)
            if self._gscn_fr_label(gscn) == key:
                return key
        return "fr1" if freq_mhz >= 3000 else "fr2"

    def _gscn_db_answer(self, gscn: int) -> str | None:
        fr = self._gscn_fr_label(gscn)
        if not fr:
            return None
        freq = gscn_to_freq(gscn, fr)
        cfg = self.db.get("gscn", {}).get(fr, {})
        return (
            f"GSCN {gscn} places the SSB at {freq:.4f} MHz "
            f"({fr.upper()} raster, step {cfg.get('step', '?')} MHz)."
        )

    def _freq_to_gscn_db(self, freq_mhz: float) -> str | None:
        if not self.db.get("gscn"):
            return None
        fr = self._gscn_fr_for_freq(freq_mhz)
        gscn = freq_to_gscn(freq_mhz, fr)
        exact = gscn_to_freq(gscn, fr)
        return (
            f"The closest GSCN to {freq_mhz:.3f} MHz is {gscn} "
            f"(SSB at {exact:.4f} MHz, {fr.upper()} raster)."
        )

    def _fcc_categories_for(self, band: str) -> list[str]:
        fcc = self.db.get("fcc", {})
        labels = {
            "licensed": "licensed spectrum",
            "unlicensed": "unlicensed spectrum",
            "shared": "shared spectrum",
            "cband": "C-Band auction spectrum",
            "mmwave": "licensed mmWave (24+ GHz) spectrum",
        }
        hits = [labels[k] for k, bands in fcc.items() if band in bands and k in labels]
        return hits

    # ------------------------------------------------------------------ #
    # Device matching helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _device_label(dev_id: str, dev: dict[str, Any]) -> str:
        return dev.get("name") or dev_id.replace("_", " ").title()

    def _device_match_keys(self, dev_id: str, dev: dict[str, Any]) -> list[str]:
        keys = [dev_id.replace("_", " ")]
        short = dev_id.split("_")[-1]
        if len(short) >= 3:
            keys.append(short)
        if dev.get("name"):
            keys.append(dev["name"].lower())
        keys += [a.lower() for a in dev.get("aliases", [])]
        return [k for k in keys if k]

    def find_device(self, query: str) -> tuple[str, dict[str, Any]] | None:
        """Match a device by id, short id (e.g. s23), name or alias."""
        q = query.lower().replace("-", " ").replace("_", " ")
        for dev_id, dev in self.devices.items():
            for key in self._device_match_keys(dev_id, dev):
                if re.search(rf"\b{re.escape(key)}\b", q) or key in q:
                    return dev_id, dev
        return None

    def find_all_devices(self, query: str) -> list[tuple[str, dict[str, Any]]]:
        q = query.lower().replace("-", " ").replace("_", " ")
        found = []
        for dev_id, dev in self.devices.items():
            if any(
                re.search(rf"\b{re.escape(key)}\b", q) or key in q
                for key in self._device_match_keys(dev_id, dev)
            ):
                found.append((dev_id, dev))
        return found

    # ------------------------------------------------------------------ #
    # 1. Device capability
    # ------------------------------------------------------------------ #
    def answer_device(self, query: str) -> str:
        ql = query.lower()

        # Comparison between two devices.
        if any(k in ql for k in ("compare", " vs ", "versus", "difference between")):
            found = self.find_all_devices(ql)
            if len(found) >= 2:
                (a_id, a), (b_id, b) = found[0], found[1]
                a_name, b_name = self._device_label(a_id, a), self._device_label(b_id, b)
                a_bands, b_bands = set(a["nr_bands"]), set(b["nr_bands"])
                only_a = sorted(a_bands - b_bands)
                only_b = sorted(b_bands - a_bands)
                return (
                    f"{a_name} vs {b_name}. "
                    f"Bands only on {a_name}: {', '.join(only_a) or 'none'}. "
                    f"Bands only on {b_name}: {', '.join(only_b) or 'none'}. "
                    f"Shared NR bands: {len(a_bands & b_bands)}."
                )

        match = self.find_device(ql)
        if not match:
            return ""
        name, info = match

        # Combo questions about a device ("Does the S23 support n77+n78 CA?")
        # are answered against the device's own combo lists.
        if _COMBO_RE.search(_normalize_combo_text(query)):
            return self.answer_ca_endc_nrdc(query)

        label = self._device_label(name, info)

        band_m = _BAND_RE.search(query)
        if band_m:
            band = band_m.group(1).lower()
            supported = band in [b.lower() for b in info["nr_bands"]]
            verdict = "supports" if supported else "does NOT support"
            return (
                f"The {label} {verdict} NR band {band}. "
                f"Supported NR bands: {', '.join(info['nr_bands'])}."
            )

        return (
            f"{label} bands: {', '.join(info['nr_bands'])}. "
            f"CA combos: {', '.join(info.get('ca', [])) or 'none'}. "
            f"EN-DC: {', '.join(info.get('endc', [])) or 'none'}. "
            f"NR-DC: {', '.join(info.get('nrdc', [])) or 'none'}."
        )

    # ------------------------------------------------------------------ #
    # 2. CA / EN-DC / NR-DC combos
    # ------------------------------------------------------------------ #
    def _section_combos(self, section: str) -> dict[str, str]:
        """Section data as combo -> note (accepts both dict and legacy list)."""
        data = self.db.get(section, {})
        if isinstance(data, dict):
            return data
        return {combo: "" for combo in data}

    def answer_ca_endc_nrdc(self, query: str) -> str:
        q = _normalize_combo_text(query)
        combos_in_q = _COMBO_RE.findall(q)

        # Device-specific combo check against the device's own ca/endc/nrdc lists.
        match = self.find_device(query)
        if match and combos_in_q:
            dev_id, info = match
            combo = max(combos_in_q, key=len)
            for key, label in _DEVICE_COMBO_KINDS:
                if combo in [c.lower() for c in info.get(key, [])]:
                    return f"Yes — the {self._device_label(dev_id, info)} supports {combo} ({label})."
            return (
                f"No — {combo} is not in the {self._device_label(dev_id, info)}'s validated combo list. "
                f"CA: {', '.join(info.get('ca', [])) or 'none'}; "
                f"EN-DC: {', '.join(info.get('endc', [])) or 'none'}; "
                f"NR-DC: {', '.join(info.get('nrdc', [])) or 'none'}."
            )

        # Network-level combo lookup; prefer the longest match so
        # "b66+n77+n261" (ENDC_FR12) wins over its "n77+n261" substring.
        matches = [
            (section, combo, note)
            for section in _COMBO_SECTIONS
            for combo, note in self._section_combos(section).items()
            if combo in q
        ]
        if matches:
            section, combo, note = max(matches, key=lambda scn: len(scn[1]))
            note_s = f" {note}." if note else ""
            return (
                f"{combo} is a supported {_SECTION_LABELS[section]} combo "
                f"({section.upper()}).{note_s}"
            )

        # Device-level CA/EN-DC capability summary.
        if match:
            dev_id, info = match
            return (
                f"{self._device_label(dev_id, info)}: "
                f"CA combos: {', '.join(info.get('ca', [])) or 'none'}. "
                f"EN-DC combos: {', '.join(info.get('endc', [])) or 'none'}. "
                f"NR-DC combos: {', '.join(info.get('nrdc', [])) or 'none'}."
            )
        return ""

    # ------------------------------------------------------------------ #
    # 3. PHY-layer math (ARFCN / GSCN / throughput)
    # ------------------------------------------------------------------ #
    def answer_phy_math(self, query: str) -> str:
        q = query.lower()
        # ARFCN → Frequency
        if "arfcn" in q:
            num = int(re.findall(r"\d+", q)[0])
            for band, info in self.db["arfcn_bands"].items():
                if abs(num - info["n_off_dl"]) < 50000:
                    return f"ARFCN {num} ≈ {arfcn_to_freq(num, info)} MHz ({band})"
        # Frequency → ARFCN (skip BW/layer/QAM throughput-style queries)
        if ("mhz" in q or "ghz" in q) and not any(
            k in q for k in ("throughput", "capacity", "layers", "qam")
        ):
            num = float(re.findall(r"\d+\.?\d*", q)[0])
            if "ghz" in q:
                num *= 1000
            band = min(
                self.db["arfcn_bands"],
                key=lambda b: abs(num - self.db["arfcn_bands"][b]["f_off_dl"]),
            )
            info = self.db["arfcn_bands"][band]
            return f"{num} MHz ≈ ARFCN {freq_to_arfcn(num, info)} ({band})"
        # GSCN
        if "gscn" in q:
            g = int(re.findall(r"\d+", q)[0])
            fr = "fr1" if g < 7500 else "fr2"
            return f"GSCN {g} → {gscn_to_freq(g, fr)} MHz ({fr.upper()})"
        # Throughput
        if "throughput" in q:
            return "Throughput engine ready — provide BW, SCS, layers, QAM."
        return ""

    # ------------------------------------------------------------------ #
    # 4. Bands / FCC regulatory
    # ------------------------------------------------------------------ #
    def answer_band_regulatory(self, query: str) -> str:
        ql = query.lower()
        fcc = self.db.get("fcc", {})

        # FCC category lookup (word-boundary match so n2 doesn't hit n260).
        if any(k in ql for k in ("fcc", "licensed", "unlicensed", "shared", "cband", "mmwave", "regulat")):
            for band_m in _BAND_RE.finditer(query):
                band = band_m.group(1).lower()
                cats = self._fcc_categories_for(band)
                if cats:
                    return f"{band} is FCC {', '.join(cats)} in the US."

        m = _BAND_RE.search(query)
        if m:
            band = m.group(1).lower()
            info = self.db.get("nr_bands", {}).get(band)
            if info:
                dl = info.get("downlink_mhz")
                ul = info.get("uplink_mhz")
                rng = f"{dl[0]}–{dl[1]} MHz" if dl else "n/a"
                ul_s = f", UL {ul[0]}–{ul[1]} MHz" if ul and ul != dl else ""
                return (
                    f"Band {band} (\"{info['common_name']}\") is a {info['duplex']} band "
                    f"in {info['frequency_range']}: DL {rng}{ul_s}. "
                    f"Typical use: {info['notes']}"
                )

        m = _LTE_BAND_RE.search(query)
        if m:
            band = f"b{m.group(1)}"
            info = self.db.get("lte_bands", {}).get(band)
            if info:
                return (
                    f"LTE Band {m.group(1)} (\"{info['common_name']}\"), {info['duplex']}: "
                    f"DL {info['downlink_mhz'][0]}–{info['downlink_mhz'][1]} MHz. "
                    f"{info['notes']}"
                )

        if "fcc" in ql or "us band" in ql:
            licensed = ", ".join(fcc.get("licensed", []))
            unlicensed = ", ".join(fcc.get("unlicensed", []))
            shared = ", ".join(fcc.get("shared", []))
            cband = ", ".join(fcc.get("cband", []))
            mmwave = ", ".join(fcc.get("mmwave", []))
            return (
                f"FCC NR spectrum in the US — licensed: {licensed}; "
                f"unlicensed: {unlicensed}; shared: {shared}; "
                f"C-Band: {cband}; mmWave: {mmwave}."
            )
        return ""

    # ------------------------------------------------------------------ #
    # Context + API helpers
    # ------------------------------------------------------------------ #
    def glossary_lookup(self, query: str) -> str:
        ql = query.lower()
        for term, definition in self.db.get("glossary", {}).items():
            if re.search(rf"\b{re.escape(term.lower())}\b", ql):
                return f"{term}: {definition}"
        return ""

    def context_for(self, query: str) -> str:
        """Assemble compact knowledge-base context for the LLM fallback."""
        parts: list[str] = []
        gloss = self.glossary_lookup(query)
        if gloss:
            parts.append(gloss)
        for m in _BAND_RE.finditer(query):
            info = self.db.get("nr_bands", {}).get(m.group(1).lower())
            if info:
                parts.append(f"{m.group(1)}: {json.dumps(info)}")
        match = self.find_device(query)
        if match:
            parts.append(f"Device: {json.dumps(match[1])}")
        return "\n".join(parts)

    def list_devices(self) -> list[dict[str, Any]]:
        return [
            {
                "id": dev_id,
                "name": self._device_label(dev_id, dev),
                "nr_bands": dev.get("nr_bands", []),
                "ca": dev.get("ca", []),
                "endc": dev.get("endc", []),
                "nrdc": dev.get("nrdc", []),
            }
            for dev_id, dev in self.devices.items()
        ]

    def list_bands(self) -> dict[str, Any]:
        return {
            "nr_bands": self.db.get("nr_bands", {}),
            "lte_bands": self.db.get("lte_bands", {}),
        }
