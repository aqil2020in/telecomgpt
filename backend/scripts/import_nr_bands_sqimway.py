"""Import all NR bands from sqimway.com (TS 38.104 tables) into nr_bands_catalog.json."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

SOURCE_URL = "https://www.sqimway.com/nr_band.php"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "nr_bands_catalog.json"
HEADERS = {"User-Agent": "TelecomGPT/1.0 (educational band catalog)"}


def _band_id(raw) -> str | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    m = re.match(r"^n(\d+)$", str(raw).strip().lower())
    return f"n{m.group(1)}" if m else None


def _cell_mhz(cell) -> float | None:
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return None
    s = str(cell).strip()
    if not s or s.lower() == "nan":
        return None
    head = s.split()[0].replace(",", "")
    try:
        val = float(head)
    except ValueError:
        return None
    if val > 100_000:
        return round(val / 1000, 3)
    return val


def _col_map(columns) -> dict[str, int]:
    """Map logical field -> column index for sqimway multi-index headers."""
    mapping: dict[str, int] = {}
    for i, col in enumerate(columns):
        parts = [str(p).strip().lower() for p in (col if isinstance(col, tuple) else (col,))]
        label = " ".join(parts)
        if label.startswith("band") and "band" not in mapping:
            mapping["band"] = i
        elif "name" in parts[:1]:
            mapping["name"] = i
        elif "mode" in parts[:1]:
            mapping["mode"] = i
        elif "δf" in label or "df raster" in label.replace(" ", ""):
            mapping["delta_f"] = i
        elif "nref" in label:
            mapping["nref"] = i
        elif "downlink" in label and "low" in parts:
            mapping["dl_low"] = i
        elif "downlink" in label and "high" in parts:
            mapping["dl_high"] = i
        elif "uplink" in label and "low" in parts:
            mapping["ul_low"] = i
        elif "uplink" in label and "high" in parts:
            mapping["ul_high"] = i
        elif "bandwidth dl/ul" in label:
            mapping["bw"] = i
        elif "duplex spacing" in label:
            mapping["duplex"] = i
        elif "geographical" in label:
            mapping["geo"] = i
        elif "3gpp release" in label:
            mapping["release"] = i
        elif label.endswith("scs (khz)") or parts[0] == "scs (khz)":
            mapping["scs"] = i
        elif "note" in parts[:1]:
            mapping["note"] = i
        elif parts[0] == "channel bandwidth (mhz)" and parts[-1].isdigit():
            mapping.setdefault("bw_cols", []).append(i)
    return mapping


def _normalize_mode(mode: str) -> str:
    m = (mode or "").strip().upper()
    for tag in ("FDD", "TDD", "SDL", "SUL"):
        if tag in m:
            return tag
    return m or "UNKNOWN"


def _fr_label(section: str, band_num: int) -> str:
    if 257 <= band_num <= 263:
        return "FR2-1"
    if 512 <= band_num <= 520:
        return "FR2-1"
    if 524 <= band_num <= 538:
        return "FR2-2"
    if 247 <= band_num <= 256:
        return "FR1-NTN"
    if section.startswith("FR2"):
        return section.replace("_", "-")
    return "FR1"


def _parse_numeric_field(val) -> float | int | str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None
    try:
        if "." in s:
            return float(s.split()[0])
        return int(float(s.split()[0]))
    except ValueError:
        return s


def parse_band_table(df: pd.DataFrame, section: str) -> dict[str, dict]:
    cmap = _col_map(df.columns)
    bands: dict[str, dict] = {}

    for _, row in df.iterrows():
        bid = _band_id(row.iloc[cmap["band"]]) if "band" in cmap else None
        if not bid:
            continue

        num = int(bid[1:])
        dl_lo = _cell_mhz(row.iloc[cmap["dl_low"]]) if "dl_low" in cmap else None
        dl_hi = _cell_mhz(row.iloc[cmap["dl_high"]]) if "dl_high" in cmap else None
        ul_lo = _cell_mhz(row.iloc[cmap["ul_low"]]) if "ul_low" in cmap else None
        ul_hi = _cell_mhz(row.iloc[cmap["ul_high"]]) if "ul_high" in cmap else None
        mode = _normalize_mode(str(row.iloc[cmap["mode"]])) if "mode" in cmap else "UNKNOWN"

        entry = bands.get(bid, {
            "common_name": str(row.iloc[cmap["name"]]).strip() if "name" in cmap else "",
            "duplex": mode,
            "frequency_range": _fr_label(section, num),
            "source": SOURCE_URL,
            "spec": "TS 38.104",
        })

        if dl_lo is not None and dl_hi is not None:
            entry["downlink_mhz"] = [min(dl_lo, dl_hi), max(dl_lo, dl_hi)]
        if mode == "FDD" and ul_lo is not None and ul_hi is not None:
            entry["uplink_mhz"] = [min(ul_lo, ul_hi), max(ul_lo, ul_hi)]
        elif mode in ("TDD", "SDL", "SUL") and dl_lo is not None and dl_hi is not None:
            entry["uplink_mhz"] = entry.get("downlink_mhz")

        for src, dst in [
            ("delta_f", "delta_f_raster_khz"),
            ("nref", "nref_step_size"),
            ("bw", "dl_ul_bandwidth_mhz"),
            ("duplex", "duplex_spacing_mhz"),
            ("geo", "geographical_area"),
            ("release", "spec_release"),
        ]:
            if src in cmap:
                v = _parse_numeric_field(row.iloc[cmap[src]])
                if v is not None:
                    entry[dst] = v

        if "scs" in cmap:
            scs = _parse_numeric_field(row.iloc[cmap["scs"]])
            if scs is not None:
                entry.setdefault("scs_khz", [])
                if isinstance(scs, int) and scs not in entry["scs_khz"]:
                    entry["scs_khz"].append(scs)

        if "bw_cols" in cmap:
            bws: list[int] = []
            for ci in cmap["bw_cols"]:
                v = row.iloc[ci]
                if pd.notna(v) and str(v).strip() not in ("", "nan"):
                    try:
                        bws.append(int(float(str(v))))
                    except ValueError:
                        pass
            if bws:
                entry["channel_bandwidth_mhz"] = sorted(set(bws))

        if "note" in cmap:
            note = row.iloc[cmap["note"]]
            if pd.notna(note) and str(note).strip():
                entry["note"] = str(note).strip()

        bands[bid] = entry

    for b in bands.values():
        if "scs_khz" in b:
            b["scs_khz"] = sorted(b["scs_khz"])
    return bands


def parse_html(html: str) -> dict[str, dict]:
    tables = pd.read_html(StringIO(html))
    all_bands: dict[str, dict] = {}
    section = "FR1"

    for df in tables:
        flat = " ".join(str(c) for c in df.columns).lower()
        if "frequency range designation" in flat:
            continue
        if "fr2-1" in flat and "band" in flat and len(df) < 30:
            section = "FR2-1"
            continue
        if "fr2-2" in flat:
            section = "FR2-2"
            continue
        if "band" not in flat or "mode" not in flat:
            continue
        # skip tiny summary tables
        if len(df) < 5:
            continue

        parsed = parse_band_table(df, section)
        for bid, info in parsed.items():
            if bid not in all_bands or len(info) >= len(all_bands[bid]):
                all_bands[bid] = {**all_bands.get(bid, {}), **info}

    return all_bands


def merge_master_notes(catalog: dict[str, dict], master_path: Path) -> dict[str, dict]:
    if not master_path.exists():
        return catalog
    master = json.loads(master_path.read_text(encoding="utf-8"))
    for bid, info in master.get("nr_bands", {}).items():
        if bid not in catalog:
            catalog[bid] = {**info, "source": SOURCE_URL, "spec": "TS 38.104"}
        elif info.get("notes"):
            catalog[bid]["notes"] = info["notes"]
    return catalog


def main() -> None:
    resp = requests.get(SOURCE_URL, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    bands = parse_html(resp.text)
    master_path = Path(__file__).resolve().parent.parent / "data" / "telecom_master_db.json"
    bands = merge_master_notes(bands, master_path)

    fr1 = sum(1 for b in bands.values() if b.get("frequency_range") == "FR1")
    fr2 = sum(1 for b in bands.values() if str(b.get("frequency_range", "")).startswith("FR2"))
    ntn = sum(1 for b in bands.values() if "NTN" in str(b.get("frequency_range", "")))

    payload = {
        "version": "1.0",
        "source": SOURCE_URL,
        "spec": "TS 38.104 (sqimway Rel 19 Dec 2025)",
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(bands),
        "fr1_count": fr1,
        "fr2_count": fr2,
        "ntn_count": ntn,
        "bands": dict(sorted(bands.items(), key=lambda x: int(x[0][1:]))),
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(bands)} NR bands to {OUT_PATH}")


if __name__ == "__main__":
    main()
