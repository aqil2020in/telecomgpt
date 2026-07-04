"""Coverage optimizer — 3-mile radius drive-test RF analysis for Google Maps."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import pandas as pd

EARTH_RADIUS_MI = 3958.8
DEFAULT_CENTER_LAT = 32.93704401921274
DEFAULT_CENTER_LON = -96.98407174060758
DEFAULT_RADIUS_MI = 3.0

_SCORE_WEIGHTS = {
    "sinr": 0.30,
    "rsrp": 0.25,
    "rsrq": 0.15,
    "bler": 0.15,
    "cqi": 0.08,
    "mcs": 0.05,
}

_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "latitude": ("latitude", "lat"),
    "longitude": ("longitude", "lon", "lng"),
    "rsrp": ("rsrp_dbm", "rsrp", "ss_rsrp", "ss-rsrp"),
    "sinr": ("sinr_db", "sinr", "ss_sinr", "ss-sinr"),
    "rsrq": ("rsrq_db", "rsrq", "ss_rsrq", "ss-rsrq"),
    "bler": ("bler_dl_pct", "bler", "dl_bler", "bler_pct"),
    "cqi": ("cqi", "avg_cqi"),
    "mcs": ("mcs_dl", "mcs", "dl_mcs"),
    "throughput": ("dl_tp_mbps", "throughput_mbps", "dl_tp", "throughput"),
    "pci": ("pci",),
    "ssb_index": ("serving_ssb", "beam_id", "ssb_index", "ssb_beam", "beam_index"),
    "timestamp": ("timestamp", "time", "period_start"),
    "coverage_status": ("coverage_status", "coverage"),
    "cell_id": ("cell_id", "cell"),
}


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(min(1.0, a)))


def parse_geo_from_query(query: str) -> tuple[float, float, float]:
    q = query
    radius = DEFAULT_RADIUS_MI
    m_radius = re.search(r"(\d+(?:\.\d+)?)\s*(?:mi(?:le)?s?|mile radius)", q, re.I)
    if m_radius:
        radius = float(m_radius.group(1))
    m_pair = re.search(r"(-?\d{1,2}\.\d{4,})\s*,\s*(-?\d{1,3}\.\d{4,})", q)
    if m_pair:
        lat, lon = float(m_pair.group(1)), float(m_pair.group(2))
        if abs(lat) <= 90 and abs(lon) <= 180:
            return lat, lon, radius
    return DEFAULT_CENTER_LAT, DEFAULT_CENTER_LON, radius


def geospatial_dataset_path() -> Path:
    from tnic.datasets.registry import datasets_dir

    candidates = [
        datasets_dir() / "enhanced_geospatial_rf_dataset.csv",
        Path(__file__).resolve().parent.parent.parent / "data" / "datasets" / "enhanced_geospatial_rf_dataset.csv",
        Path("/workspace/datasets/enhanced_geospatial_rf_dataset.csv"),
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("enhanced_geospatial_rf_dataset.csv not found")


def detect_rf_columns(df: pd.DataFrame) -> dict[str, str | None]:
    cols_lower = {str(c).lower(): str(c) for c in df.columns}
    out: dict[str, str | None] = {}
    for key, aliases in _COLUMN_ALIASES.items():
        found = None
        for alias in aliases:
            if alias in cols_lower:
                found = cols_lower[alias]
                break
        out[key] = found
    return out


def _norm_higher(value: float, good: float, fair: float, poor: float) -> float:
    if value >= good:
        return 100.0
    if value >= fair:
        return 60.0 + 40.0 * (value - fair) / max(good - fair, 1e-6)
    if value >= poor:
        return 20.0 + 40.0 * (value - poor) / max(fair - poor, 1e-6)
    return max(0.0, 20.0 * (value - poor - 10) / max(-poor - 10, 1e-6))


def _norm_lower(value: float, good: float, fair: float, poor: float) -> float:
    return _norm_higher(-value, -good, -fair, -poor)


def _subscore(name: str, value: float) -> float | None:
    if name == "rsrp":
        return _norm_higher(value, -80, -95, -110)
    if name == "sinr":
        return _norm_higher(value, 20, 10, 0)
    if name == "rsrq":
        return _norm_higher(value, -8, -12, -18)
    if name == "bler":
        return _norm_lower(value, 1, 5, 12)
    if name == "cqi":
        return _norm_higher(value, 12, 8, 4)
    if name == "mcs":
        return _norm_higher(value, 22, 14, 6)
    return None


def _composite_row(row: pd.Series, rf: dict[str, str | None]) -> tuple[float, dict[str, float]]:
    parts: dict[str, float] = {}
    total = 0.0
    weight_sum = 0.0
    for name, weight in _SCORE_WEIGHTS.items():
        col = rf.get(name)
        if not col or col not in row.index or pd.isna(row[col]):
            continue
        try:
            val = float(row[col])
        except (TypeError, ValueError):
            continue
        sub = _subscore(name, val)
        if sub is None:
            continue
        parts[name] = round(sub, 1)
        total += weight * sub
        weight_sum += weight
    score = total / weight_sum if weight_sum else 0.0
    return round(score, 1), parts


def _idw_predict(
    df: pd.DataFrame,
    lat_col: str,
    lon_col: str,
    value_col: str,
    grid_lats: list[float],
    grid_lons: list[float],
    *,
    power: float = 2.0,
) -> list[float]:
    preds: list[float] = []
    vals = pd.to_numeric(df[value_col], errors="coerce")
    for glat, glon in zip(grid_lats, grid_lons):
        vsum = wsum = 0.0
        exact = None
        for _, row in df.iterrows():
            v = vals.loc[row.name] if row.name in vals.index else None
            if v is None or pd.isna(v):
                continue
            d = haversine_miles(glat, glon, float(row[lat_col]), float(row[lon_col]))
            if d < 0.01:
                exact = float(v)
                break
            w = 1.0 / (d ** power)
            vsum += w * float(v)
            wsum += w
        preds.append(exact if exact is not None else (vsum / wsum if wsum else float("nan")))
    return preds


def _row_payload(row: pd.Series, lat_col: str, lon_col: str, rf: dict[str, str | None]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "latitude": round(float(row[lat_col]), 6),
        "longitude": round(float(row[lon_col]), 6),
        "distance_mi": round(float(row["_dist_mi"]), 2),
        "rf_score": float(row["_rf_score"]),
        "score_breakdown": row.get("_score_parts") or {},
    }
    for k, col in rf.items():
        if col and col in row.index and pd.notna(row[col]) and k in (
            "rsrp", "rsrq", "sinr", "cqi", "bler", "throughput", "pci", "coverage_status", "cell_id"
        ):
            try:
                payload[k] = float(row[col]) if k not in ("pci", "coverage_status", "cell_id") else row[col]
            except (TypeError, ValueError):
                payload[k] = row[col]
    ssb = rf.get("ssb_index")
    if ssb and ssb in row.index and pd.notna(row[ssb]):
        payload["ssb_beam"] = row[ssb]
    return payload


def _drive_route_points(
    df: pd.DataFrame,
    lat_col: str,
    lon_col: str,
    rf: dict[str, str | None],
) -> list[dict[str, Any]]:
    route_df = df.dropna(subset=[lat_col, lon_col]).copy()
    ts = rf.get("timestamp")
    if ts and ts in route_df.columns:
        route_df = route_df.sort_values(ts)
    points: list[dict[str, Any]] = []
    for _, row in route_df.iterrows():
        p: dict[str, Any] = {
            "latitude": round(float(row[lat_col]), 6),
            "longitude": round(float(row[lon_col]), 6),
            "rf_score": float(row["_rf_score"]) if "_rf_score" in row.index else None,
        }
        for k in ("rsrp", "sinr", "rsrq", "coverage_status"):
            col = rf.get(k) if k != "coverage_status" else rf.get("coverage_status")
            if k == "coverage_status":
                col = rf.get("coverage_status")
            if col and col in row.index and pd.notna(row[col]):
                try:
                    p[k] = float(row[col]) if k != "coverage_status" else row[col]
                except (TypeError, ValueError):
                    p[k] = row[col]
        points.append(p)
    return points


def infer_site_center(df: pd.DataFrame, rf: dict[str, str | None]) -> tuple[float, float]:
    lat_col, lon_col = rf.get("latitude"), rf.get("longitude")
    if lat_col and lon_col and not df.empty:
        if "distance_miles" in df.columns:
            near = df.nsmallest(max(5, len(df) // 20), "distance_miles")
            return float(near[lat_col].mean()), float(near[lon_col].mean())
        return float(df[lat_col].mean()), float(df[lon_col].mean())
    return DEFAULT_CENTER_LAT, DEFAULT_CENTER_LON


def optimize_coverage(
    path: str | Path | None = None,
    *,
    center_lat: float | None = None,
    center_lon: float | None = None,
    radius_miles: float = DEFAULT_RADIUS_MI,
    top_n: int = 10,
    suggest_n: int = 5,
) -> dict[str, Any]:
    """Analyze geospatial drive-test CSV within radius; return map-ready payload."""
    csv_path = Path(path) if path else geospatial_dataset_path()
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower() for c in df.columns]
    rf = detect_rf_columns(df)

    lat_col = rf.get("latitude")
    lon_col = rf.get("longitude")
    if not lat_col or not lon_col:
        return {
            "ok": False,
            "error": "CSV needs latitude and longitude columns.",
            "center": {"lat": center_lat or DEFAULT_CENTER_LAT, "lon": center_lon or DEFAULT_CENTER_LON, "radius_miles": radius_miles},
        }

    if center_lat is None or center_lon is None:
        center_lat, center_lon = infer_site_center(df, rf)

    work = df.copy()
    if "distance_miles" in work.columns:
        work["_dist_mi"] = pd.to_numeric(work["distance_miles"], errors="coerce")
    else:
        work["_dist_mi"] = work.apply(
            lambda r: haversine_miles(center_lat, center_lon, float(r[lat_col]), float(r[lon_col]))
            if pd.notna(r[lat_col]) and pd.notna(r[lon_col])
            else float("nan"),
            axis=1,
        )

    in_radius = work[work["_dist_mi"] <= radius_miles].dropna(subset=[lat_col, lon_col]).copy()
    if in_radius.empty:
        return {
            "ok": False,
            "error": f"No measurements within {radius_miles} mi of site center.",
            "center": {"lat": center_lat, "lon": center_lon, "radius_miles": radius_miles},
            "total_rows": len(df),
        }

    scores, breakdowns = [], []
    for _, row in in_radius.iterrows():
        s, bd = _composite_row(row, rf)
        scores.append(s)
        breakdowns.append(bd)
    in_radius["_rf_score"] = scores
    in_radius["_score_parts"] = breakdowns

    rsrp_col = rf.get("rsrp")
    if rsrp_col:
        idx = in_radius.groupby([lat_col, lon_col])[rsrp_col].idxmax()
        deduped = in_radius.loc[idx].copy()
    else:
        deduped = in_radius.sort_values("_rf_score", ascending=False).drop_duplicates(
            subset=[lat_col, lon_col], keep="first"
        )

    ranked = deduped.sort_values("_rf_score", ascending=False)
    weak = ranked[
        (ranked["_rf_score"] < 40)
        | ((rsrp_col and pd.to_numeric(ranked[rsrp_col], errors="coerce") < -108))
        | ((rf.get("sinr") and pd.to_numeric(ranked[rf["sinr"]], errors="coerce") < 5))
    ].head(12)

    cov_col = rf.get("coverage_status")
    holes = []
    if cov_col and cov_col in in_radius.columns:
        holes_df = in_radius[in_radius[cov_col].astype(str).str.contains("hole|poor", case=False, na=False)]
        holes = [_row_payload(row, lat_col, lon_col, rf) for _, row in holes_df.head(10).iterrows()]

    suggested: list[dict[str, Any]] = []
    sinr_col = rf.get("sinr")
    if sinr_col and len(in_radius) >= 15:
        step = 0.005
        grid_lats, grid_lons = [], []
        for dlat in [i * step for i in range(-12, 13)]:
            for dlon in [i * step for i in range(-12, 13)]:
                glat, glon = center_lat + dlat, center_lon + dlon
                if haversine_miles(center_lat, center_lon, glat, glon) <= radius_miles:
                    grid_lats.append(glat)
                    grid_lons.append(glon)
        if grid_lats:
            pred_sinr = _idw_predict(in_radius, lat_col, lon_col, sinr_col, grid_lats, grid_lons)
            measured = {(round(float(r[lat_col]), 4), round(float(r[lon_col]), 4)) for _, r in ranked.iterrows()}
            candidates = []
            for glat, glon, ps in zip(grid_lats, grid_lons, pred_sinr):
                if math.isnan(ps):
                    continue
                if (round(glat, 4), round(glon, 4)) in measured:
                    continue
                nearest = min(
                    haversine_miles(glat, glon, float(r[lat_col]), float(r[lon_col]))
                    for _, r in in_radius.iterrows()
                )
                if nearest < 0.15:
                    continue
                candidates.append({
                    "latitude": round(glat, 6),
                    "longitude": round(glon, 6),
                    "distance_mi": round(haversine_miles(center_lat, center_lon, glat, glon), 2),
                    "predicted_sinr_db": round(ps, 1),
                    "predicted_score": round(_norm_higher(ps, 20, 10, 0), 1),
                    "confidence": "medium" if len(in_radius) >= 40 else "low",
                    "nearest_sample_mi": round(nearest, 2),
                })
            suggested = sorted(candidates, key=lambda x: x["predicted_score"], reverse=True)[:suggest_n]

    return {
        "ok": True,
        "center": {"lat": center_lat, "lon": center_lon, "radius_miles": radius_miles},
        "points_in_radius": len(in_radius),
        "unique_locations": len(deduped),
        "best_measured": [_row_payload(row, lat_col, lon_col, rf) for _, row in ranked.head(top_n).iterrows()],
        "weak_zones": [_row_payload(row, lat_col, lon_col, rf) for _, row in weak.iterrows()],
        "coverage_holes": holes,
        "suggested_verify": suggested,
        "coverage_status_mix": (
            in_radius[cov_col].value_counts().to_dict() if cov_col and cov_col in in_radius.columns else {}
        ),
        "rf_columns": {k: v for k, v in rf.items() if v},
        "source": csv_path.name,
        "csv_path": str(csv_path),
        "drive_route": _drive_route_points(in_radius, lat_col, lon_col, rf),
    }
