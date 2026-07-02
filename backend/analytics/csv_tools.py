"""CSV loading and summary statistics."""

from __future__ import annotations

import io
import re
from typing import Any

import pandas as pd


def load_csv_bytes(raw: bytes, *, encoding: str = "utf-8") -> pd.DataFrame:
    for enc in (encoding, "utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(io.BytesIO(raw), encoding=encoding, errors="replace")


def load_csv_path(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


# Common Kaggle / drive-test column aliases
_RF_ALIASES: dict[str, tuple[str, ...]] = {
    "latitude": ("latitude", "lat", "Latitude", "LAT"),
    "longitude": ("longitude", "lon", "lng", "Longitude", "LON"),
    "rsrp": (
        "rsrp", "RSRP", "rsrp_dbm", "SS-RSRP", "ss_rsrp", "RSRP_dBm", "SS RSRP",
        "Signal Strength (dBm)", "signal strength (dbm)", "Signal Strength",
    ),
    "rsrq": ("rsrq", "RSRQ", "rsrq_db", "SS-RSRQ", "ss_rsrq", "SS RSRQ"),
    "sinr": ("sinr", "SINR", "snr", "SNR", "ss_sinr", "SS-SINR", "SS SINR"),
    "rssi": ("rssi", "RSSI", "rssi_dbm"),
    "cqi": ("cqi", "CQI", "wideband_cqi", "WB CQI"),
    "bler": ("bler", "BLER", "block error rate", "block_error_rate"),
    "ri": ("ri", "RI", "rank indicator", "rank_indicator", "Rank Indicator"),
    "mcs_dl": ("mcs_dl", "MCS DL", "dl_mcs", "mcs downlink"),
    "mcs_ul": ("mcs_ul", "MCS UL", "ul_mcs", "mcs uplink"),
    "throughput": (
        "throughput", "target", "App. rate DL", "dl_throughput", "throughput_mbps",
        "Download Speed (Mbps)", "download speed (mbps)", "Download Speed",
    ),
    "throughput_ul": (
        "upload_throughput", "ul_throughput", "Upload Speed (Mbps)",
        "upload speed (mbps)", "Upload Speed",
    ),
    "latency": ("latency", "Latency (ms)", "latency_ms", "Latency"),
    "jitter": ("jitter", "Jitter (ms)", "jitter_ms"),
    "band": ("band", "Band", "nr_band", "lte_band"),
    "pci": ("pci", "PCI", "cid", "cell_id"),
    "ssb_index": ("ssb_index", "SSB_INDEX", "SSB Index", "ssb_idx", "ssb_beam", "beam_id", "beam_index"),
    "arfcn": ("arfcn", "nr_arfcn", "NR-ARFCN", "earfcn", "freq"),
}


def _fuzzy_column_match(alias: str, col_lower: str) -> bool:
    a = alias.lower().replace(" ", "")
    c = col_lower.replace(" ", "")
    if a == c:
        return True
    if len(a) < 4:
        return False
    return a in c


def detect_rf_columns(df: pd.DataFrame) -> dict[str, str | None]:
    cols = {str(c).strip(): str(c) for c in df.columns}
    lower_map = {k.lower(): v for k, v in cols.items()}
    out: dict[str, str | None] = {}
    used: set[str] = set()
    for key, aliases in _RF_ALIASES.items():
        found = None
        for alias in aliases:
            if alias in cols:
                found = cols[alias]
                break
            if alias.lower() in lower_map:
                found = lower_map[alias.lower()]
                break
        if not found:
            for alias in aliases:
                for col_lower, col_orig in lower_map.items():
                    if col_orig in used:
                        continue
                    if _fuzzy_column_match(alias, col_lower):
                        found = col_orig
                        break
                if found:
                    break
        if found:
            used.add(found)
        out[key] = found
    return out


def csv_summary(df: pd.DataFrame, *, sample_rows: int = 5) -> dict[str, Any]:
    numeric = df.select_dtypes(include="number")
    describe = numeric.describe().round(4).to_dict() if not numeric.empty else {}
    rf = detect_rf_columns(df)

    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "column_names": list(df.columns.astype(str)),
        "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
        "null_counts": {str(c): int(v) for c, v in df.isna().sum().items()},
        "numeric_summary": describe,
        "preview": df.head(sample_rows).astype(str).to_dict(orient="records"),
        "numeric_columns": [str(c) for c in numeric.columns],
        "categorical_columns": [
            str(c) for c in df.columns if c not in numeric.columns
        ],
        "rf_columns": rf,
        "has_gps": bool(rf.get("latitude") and rf.get("longitude")),
    }

