"""Coverage optimizer — rank RF quality and suggest better UE locations within a radius."""

from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd

from .csv_tools import detect_rf_columns, load_csv_path

EARTH_RADIUS_MI = 3958.8

# Default pilot site (user-provided)
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
    "ri": 0.02,
}


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(min(1.0, a)))


def parse_geo_from_query(query: str) -> tuple[float, float, float]:
    """Extract center lat/lon and radius miles from natural language."""
    q = query
    radius = DEFAULT_RADIUS_MI
    m_radius = re.search(r"(\d+(?:\.\d+)?)\s*(?:mi(?:le)?s?|mile radius)", q, re.I)
    if m_radius:
        radius = float(m_radius.group(1))

    # Decimal pair: lat, lon (lat typically 25-50 for US, lon negative for US)
    m_pair = re.search(
        r"(-?\d{1,2}\.\d{4,})\s*,\s*(-?\d{1,3}\.\d{4,})",
        q,
    )
    if m_pair:
        lat, lon = float(m_pair.group(1)), float(m_pair.group(2))
        if abs(lat) <= 90 and abs(lon) <= 180:
            return lat, lon, radius

    return DEFAULT_CENTER_LAT, DEFAULT_CENTER_LON, radius


def looks_like_coverage_optimizer_query(query: str) -> bool:
    ql = query.lower()
    keys = (
        "coverage optimizer",
        "better coverage",
        "best location",
        "best locations",
        "where is coverage better",
        "predict coverage",
        "recommend location",
        "rf coverage radius",
        "mile radius",
        "miles radius",
        "coverage radius",
        "weak zone",
        "coverage hole",
        "drive route map",
        "drive route",
    )
    if any(k in ql for k in keys):
        return True
    # lat,lon + radius or coverage-ish words
    if re.search(r"-?\d{1,2}\.\d{4,}\s*,\s*-\d{1,3}\.\d{4,}", query):
        if any(w in ql for w in ("mile", "radius", "coverage", "rsrp", "sinr", "location")):
            return True
    return False


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
    if name == "ri":
        return _norm_higher(value, 4, 2, 1)
    return None


def _composite_row(row: pd.Series, rf: dict[str, str | None]) -> tuple[float, dict[str, float]]:
    parts: dict[str, float] = {}
    total_w = 0.0
    score = 0.0
    for key, weight in _SCORE_WEIGHTS.items():
        col = rf.get(key) or (rf.get("mcs_dl") if key == "mcs" else None)
        if not col or col not in row.index or pd.isna(row[col]):
            continue
        try:
            val = float(row[col])
        except (TypeError, ValueError):
            continue
        sub = _subscore(key if key != "mcs" else "mcs", val)
        if sub is None:
            continue
        parts[key] = round(sub, 1)
        score += weight * sub
        total_w += weight
    if total_w == 0:
        return 0.0, parts
    return round(score / total_w, 1), parts


def _ssb_column(df: pd.DataFrame, rf: dict[str, str | None]) -> str | None:
    if rf.get("ssb_index"):
        return rf["ssb_index"]
    for c in df.columns:
        cl = str(c).lower().replace(" ", "_")
        if cl in ("ssb_index", "ssb_idx", "ssb_beam", "ssb", "beam_id", "beam_index"):
            return str(c)
    return None


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
        weights = []
        vsum = 0.0
        wsum = 0.0
        for _, row in df.iterrows():
            v = vals.loc[row.name] if row.name in vals.index else None
            if v is None or pd.isna(v):
                continue
            d = haversine_miles(glat, glon, float(row[lat_col]), float(row[lon_col]))
            if d < 0.01:
                preds.append(float(v))
                vsum = wsum = 0.0
                break
            w = 1.0 / (d ** power)
            vsum += w * float(v)
            wsum += w
        else:
            preds.append(vsum / wsum if wsum > 0 else float("nan"))
    return preds


def optimize_coverage(
    path: str,
    *,
    center_lat: float | None = None,
    center_lon: float | None = None,
    radius_miles: float = DEFAULT_RADIUS_MI,
    top_n: int = 10,
    suggest_n: int = 5,
) -> dict[str, Any]:
    """Analyze drive-test CSV; return best measured + optional interpolated locations."""
    center_lat = center_lat if center_lat is not None else DEFAULT_CENTER_LAT
    center_lon = center_lon if center_lon is not None else DEFAULT_CENTER_LON

    df = load_csv_path(path)
    rf = detect_rf_columns(df)
    lat_col = rf.get("latitude")
    lon_col = rf.get("longitude")
    if not lat_col or not lon_col:
        return {
            "ok": False,
            "error": "CSV needs latitude and longitude columns for coverage optimization.",
            "center": {"lat": center_lat, "lon": center_lon, "radius_miles": radius_miles},
        }

    work = df.copy()
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
            "error": f"No measurements within {radius_miles} mi of ({center_lat:.6f}, {center_lon:.6f}).",
            "center": {"lat": center_lat, "lon": center_lon, "radius_miles": radius_miles},
            "total_rows": len(df),
        }

    scores: list[float] = []
    breakdowns: list[dict] = []
    for _, row in in_radius.iterrows():
        s, bd = _composite_row(row, rf)
        scores.append(s)
        breakdowns.append(bd)
    in_radius["_rf_score"] = scores
    in_radius["_score_parts"] = breakdowns

    ssb_col = _ssb_column(in_radius, rf)
    if ssb_col:
        in_radius["_loc_key"] = (
            in_radius[lat_col].round(5).astype(str) + "," + in_radius[lon_col].round(5).astype(str)
        )
        # Per location keep best beam row by RSRP if available
        rsrp_col = rf.get("rsrp")
        if rsrp_col:
            idx = in_radius.groupby("_loc_key")[rsrp_col].idxmax()
            deduped = in_radius.loc[idx].copy()
        else:
            idx = in_radius.groupby("_loc_key")["_rf_score"].idxmax()
            deduped = in_radius.loc[idx].copy()
    else:
        deduped = in_radius.sort_values("_rf_score", ascending=False).drop_duplicates(
            subset=[lat_col, lon_col], keep="first"
        )

    ranked = deduped.sort_values("_rf_score", ascending=False)
    top_rows = ranked.head(top_n)

    weak = ranked[
        (ranked["_rf_score"] < 40)
        | (
            (rf.get("rsrp") and pd.to_numeric(ranked[rf["rsrp"]], errors="coerce") < -108)
        )
        | (
            (rf.get("sinr") and pd.to_numeric(ranked[rf["sinr"]], errors="coerce") < 5)
        )
    ].head(10)

    def _row_payload(row: pd.Series) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "latitude": round(float(row[lat_col]), 6),
            "longitude": round(float(row[lon_col]), 6),
            "distance_mi": round(float(row["_dist_mi"]), 2),
            "rf_score": float(row["_rf_score"]),
            "score_breakdown": row.get("_score_parts") or {},
        }
        for k, col in rf.items():
            if col and col in row.index and pd.notna(row[col]) and k in (
                "rsrp", "rsrq", "sinr", "cqi", "bler", "ri", "mcs_dl", "throughput", "pci"
            ):
                try:
                    payload[k] = float(row[col]) if k != "pci" else row[col]
                except (TypeError, ValueError):
                    payload[k] = row[col]
        if ssb_col and ssb_col in row.index and pd.notna(row[ssb_col]):
            payload["ssb_beam"] = row[ssb_col]
        return payload

    best_measured = [_row_payload(row) for _, row in top_rows.iterrows()]
    weak_zones = [_row_payload(row) for _, row in weak.iterrows()]

    suggested: list[dict[str, Any]] = []
    if len(in_radius) >= 15 and rf.get("sinr"):
        sinr_col = rf["sinr"]
        # coarse grid inside radius (~0.35 mi step)
        step = 0.005
        grid_lats, grid_lons = [], []
        lat0, lon0 = center_lat, center_lon
        for dlat in [i * step for i in range(-int(radius_miles / 0.35), int(radius_miles / 0.35) + 1)]:
            for dlon in [i * step for i in range(-int(radius_miles / 0.35), int(radius_miles / 0.35) + 1)]:
                glat, glon = lat0 + dlat, lon0 + dlon
                if haversine_miles(lat0, lon0, glat, glon) <= radius_miles:
                    grid_lats.append(glat)
                    grid_lons.append(glon)
        if grid_lats:
            pred_sinr = _idw_predict(in_radius, lat_col, lon_col, sinr_col, grid_lats, grid_lons)
            candidates = []
            measured_set = {
                (round(float(r[lat_col]), 4), round(float(r[lon_col]), 4))
                for _, r in ranked.iterrows()
            }
            for glat, glon, ps in zip(grid_lats, grid_lons, pred_sinr):
                if math.isnan(ps):
                    continue
                key = (round(glat, 4), round(glon, 4))
                if key in measured_set:
                    continue
                # min 0.15 mi from nearest sample to be a "new" suggestion
                nearest = min(
                    haversine_miles(glat, glon, float(r[lat_col]), float(r[lon_col]))
                    for _, r in in_radius.iterrows()
                )
                if nearest < 0.15:
                    continue
                pred_score = _norm_higher(ps, 20, 10, 0)
                candidates.append({
                    "latitude": round(glat, 6),
                    "longitude": round(glon, 6),
                    "distance_mi": round(haversine_miles(lat0, lon0, glat, glon), 2),
                    "predicted_sinr_db": round(ps, 1),
                    "predicted_score": round(pred_score, 1),
                    "confidence": "medium" if len(in_radius) >= 40 else "low",
                    "nearest_sample_mi": round(nearest, 2),
                })
            suggested = sorted(candidates, key=lambda x: x["predicted_score"], reverse=True)[:suggest_n]

    return {
        "ok": True,
        "center": {"lat": center_lat, "lon": center_lon, "radius_miles": radius_miles},
        "points_in_radius": len(in_radius),
        "unique_locations": len(deduped),
        "best_measured": best_measured,
        "weak_zones": weak_zones,
        "suggested_verify": suggested,
        "rf_columns": {k: v for k, v in rf.items() if v},
        "source": path.split("/")[-1].split("\\")[-1],
        "csv_path": path,
        "drive_route": _drive_route_points(in_radius, lat_col, lon_col, rf),
    }


def format_coverage_report(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        err = result.get("error", "Coverage optimization failed.")
        c = result.get("center", {})
        return (
            f"# Coverage optimizer\n\n**Error:** {err}\n\n"
            f"Center: `{c.get('lat')}, {c.get('lon')}` · radius **{c.get('radius_miles', 3)} mi**\n\n"
            "Upload a drive-test CSV with `latitude`, `longitude`, RSRP, SINR, RSRQ, CQI, MCS, BLER, RI, SSB beam."
        )

    c = result["center"]
    lines = [
        "# Coverage optimizer report",
        "",
        f"**Center:** `{c['lat']:.6f}, {c['lon']:.6f}`",
        f"**Radius:** {c['radius_miles']} miles",
        f"**Samples in radius:** {result['points_in_radius']} ({result['unique_locations']} unique locations)",
        f"**Source:** `{result.get('source', 'uploaded CSV')}`",
        "",
        "Composite score weights: SINR 30%, RSRP 25%, RSRQ 15%, BLER 15%, CQI 8%, MCS 5%, RI 2%.",
        "",
        "## Top locations — measured (high confidence)",
        "",
        "| Rank | Lat | Lon | Dist (mi) | Score | SINR | RSRP | RSRQ | BLER | SSB |",
        "|------|-----|-----|-----------|-------|------|------|------|------|-----|",
    ]
    for i, row in enumerate(result.get("best_measured") or [], 1):
        lines.append(
            f"| {i} | {row['latitude']} | {row['longitude']} | {row['distance_mi']} | "
            f"**{row['rf_score']}** | {row.get('sinr', '—')} | {row.get('rsrp', '—')} | "
            f"{row.get('rsrq', '—')} | {row.get('bler', '—')} | {row.get('ssb_beam', '—')} |"
        )

    suggested = result.get("suggested_verify") or []
    if suggested:
        lines.extend([
            "",
            "## Suggested verify locations — interpolated (medium/low confidence)",
            "",
            "Go to these coordinates to **confirm** predicted coverage (IDW from your samples).",
            "",
            "| Lat | Lon | Dist (mi) | Pred SINR | Pred score | Nearest sample (mi) | Confidence |",
            "|-----|-----|-----------|-----------|------------|---------------------|------------|",
        ])
        for row in suggested:
            lines.append(
                f"| {row['latitude']} | {row['longitude']} | {row['distance_mi']} | "
                f"{row['predicted_sinr_db']} dB | {row['predicted_score']} | "
                f"{row['nearest_sample_mi']} | {row['confidence']} |"
            )

    weak = result.get("weak_zones") or []
    if weak:
        lines.extend(["", "## Weak zones — avoid / investigate", ""])
        for row in weak[:5]:
            lines.append(
                f"- `{row['latitude']}, {row['longitude']}` — score **{row['rf_score']}**, "
                f"RSRP {row.get('rsrp', '—')}, SINR {row.get('sinr', '—')} dB"
            )

    lines.extend([
        "",
        "## Drive route map (Google Maps)",
        "",
        "Open the **Drive route map** below on Google Maps: **gray route** = drive path · "
        "**green markers** = best UE locations · **red** = weak zones · "
        "**blue** = suggested verify · **purple** = site center · "
        f"**indigo circle** = {c['radius_miles']} mi radius.",
        "",
        "Requires `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` on Vercel (Maps JavaScript API enabled).",
        "",
        "## How to use",
        "",
        "1. **Best measured** — relocate UE test to top-ranked lat/lon.",
        "2. **Suggested verify** — drive/walk to predicted spots and add rows to CSV.",
        "3. **Weak zones** — check clutter, tilt, neighbor PCI, or beam selection.",
    ])
    return "\n".join(lines)


def explain_coverage_optimizer(
    query: str,
    *,
    csv_path: str | None = None,
    session_id: str = "default",
) -> str:
    from pathlib import Path

    lat, lon, radius = parse_geo_from_query(query)
    path = csv_path
    if not path:
        uploads = Path(__file__).resolve().parent.parent / "data" / "uploads" / session_id
        if uploads.exists():
            csvs = sorted(uploads.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
            if csvs:
                path = str(csvs[0])
        if not path:
            sample = Path(__file__).resolve().parent.parent / "data" / "samples" / "coverage_dallas_3mi.csv"
            if sample.exists():
                path = str(sample)

    if not path:
        return format_coverage_report({
            "ok": False,
            "error": "No CSV found. Upload drive-test CSV with GPS + RF KPIs.",
            "center": {"lat": lat, "lon": lon, "radius_miles": radius},
        })

    result = optimize_coverage(path, center_lat=lat, center_lon=lon, radius_miles=radius)
    return format_coverage_report(result)


def _timestamp_column(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        if str(c).lower() in ("timestamp", "time", "datetime", "date_time"):
            return str(c)
    return None


def _drive_route_points(
    df: pd.DataFrame,
    lat_col: str,
    lon_col: str,
    rf: dict[str, str | None],
) -> list[dict[str, Any]]:
    """GPS points in drive order for route map."""
    route_df = df.dropna(subset=[lat_col, lon_col]).copy()
    ts = _timestamp_column(route_df)
    if ts:
        route_df = route_df.sort_values(ts)
    points: list[dict[str, Any]] = []
    for _, row in route_df.iterrows():
        p: dict[str, Any] = {
            "latitude": round(float(row[lat_col]), 6),
            "longitude": round(float(row[lon_col]), 6),
            "rf_score": float(row["_rf_score"]) if "_rf_score" in row.index else None,
        }
        for k in ("rsrp", "sinr", "rsrq"):
            col = rf.get(k)
            if col and col in row.index and pd.notna(row[col]):
                try:
                    p[k] = float(row[col])
                except (TypeError, ValueError):
                    pass
        points.append(p)
    return points


def _circle_lat_lon(center_lat: float, center_lon: float, radius_mi: float, n: int = 72) -> tuple[list[float], list[float]]:
    lats: list[float] = []
    lons: list[float] = []
    for i in range(n + 1):
        bearing = 2 * math.pi * i / n
        ang_dist = radius_mi / EARTH_RADIUS_MI
        rlat1 = math.radians(center_lat)
        rlon1 = math.radians(center_lon)
        rlat2 = math.asin(
            math.sin(rlat1) * math.cos(ang_dist)
            + math.cos(rlat1) * math.sin(ang_dist) * math.cos(bearing)
        )
        rlon2 = rlon1 + math.atan2(
            math.sin(bearing) * math.sin(ang_dist) * math.cos(rlat1),
            math.cos(ang_dist) - math.sin(rlat1) * math.sin(rlat2),
        )
        lats.append(math.degrees(rlat2))
        lons.append(math.degrees(rlon2))
    return lats, lons


def build_coverage_drive_route_chart(result: dict[str, Any]) -> dict[str, Any] | None:
    """Plotly drive-route map: route line, RF-colored samples, best/weak/suggested pins, radius ring."""
    if not result.get("ok"):
        return None

    import plotly.graph_objects as go

    c = result["center"]
    clat, clon, radius = c["lat"], c["lon"], c["radius_miles"]
    route = result.get("drive_route") or []
    traces: list[Any] = []

    # 3-mile radius ring
    ring_lats, ring_lons = _circle_lat_lon(clat, clon, radius)
    traces.append(
        go.Scattergeo(
            lat=ring_lats,
            lon=ring_lons,
            mode="lines",
            line=dict(width=2, color="#6366f1"),
            name=f"{radius} mi radius",
            hoverinfo="skip",
        )
    )

    # Drive route polyline (timestamp order)
    if len(route) >= 2:
        traces.append(
            go.Scattergeo(
                lat=[p["latitude"] for p in route],
                lon=[p["longitude"] for p in route],
                mode="lines+markers",
                line=dict(width=3, color="#94a3b8"),
                marker=dict(size=5, color="#64748b"),
                name="Drive route",
                text=[
                    f"RSRP {p.get('rsrp', '—')} · SINR {p.get('sinr', '—')} · score {p.get('rf_score', '—')}"
                    for p in route
                ],
                hoverinfo="text",
            )
        )
    elif route:
        traces.append(
            go.Scattergeo(
                lat=[route[0]["latitude"]],
                lon=[route[0]["longitude"]],
                mode="markers",
                marker=dict(size=8, color="#64748b"),
                name="Drive sample",
            )
        )

    # Best UE locations (top 5)
    best = result.get("best_measured") or []
    if best:
        traces.append(
            go.Scattergeo(
                lat=[p["latitude"] for p in best[:5]],
                lon=[p["longitude"] for p in best[:5]],
                mode="markers+text",
                marker=dict(size=14, color="#16a34a", symbol="star"),
                text=[f"#{i + 1}" for i in range(min(5, len(best)))],
                textposition="top center",
                name="Best UE locations",
                hovertext=[
                    f"Rank {i + 1}: score {p['rf_score']} · SINR {p.get('sinr', '—')} · RSRP {p.get('rsrp', '—')}"
                    for i, p in enumerate(best[:5])
                ],
                hoverinfo="text",
            )
        )

    # Weak zones
    weak = result.get("weak_zones") or []
    if weak:
        traces.append(
            go.Scattergeo(
                lat=[p["latitude"] for p in weak[:5]],
                lon=[p["longitude"] for p in weak[:5]],
                mode="markers",
                marker=dict(size=11, color="#dc2626", symbol="x"),
                name="Weak zones",
                hovertext=[
                    f"Weak: score {p['rf_score']} · RSRP {p.get('rsrp', '—')}"
                    for p in weak[:5]
                ],
                hoverinfo="text",
            )
        )

    # Suggested verify
    suggested = result.get("suggested_verify") or []
    if suggested:
        traces.append(
            go.Scattergeo(
                lat=[p["latitude"] for p in suggested],
                lon=[p["longitude"] for p in suggested],
                mode="markers",
                marker=dict(size=12, color="#2563eb", symbol="diamond"),
                name="Suggested verify",
                hovertext=[
                    f"Pred SINR {p.get('predicted_sinr_db', '—')} dB · {p.get('confidence', '')}"
                    for p in suggested
                ],
                hoverinfo="text",
            )
        )

    # Site center
    traces.append(
        go.Scattergeo(
            lat=[clat],
            lon=[clon],
            mode="markers+text",
            marker=dict(size=13, color="#7c3aed", symbol="circle"),
            text=["Site"],
            textposition="bottom center",
            name="Center",
            hovertext=[f"Center {clat:.5f}, {clon:.5f} · {radius} mi"],
            hoverinfo="text",
        )
    )

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=f"Drive route map — coverage optimizer ({radius} mi)",
        height=520,
        margin=dict(l=20, r=20, t=56, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        geo=dict(
            scope="usa",
            projection_type="albers usa",
            showland=True,
            landcolor="#f1f5f9",
            subunitcolor="#cbd5e1",
            center=dict(lat=clat, lon=clon),
            projection_scale=12,
        ),
    )
    fig.update_geos(fitbounds="locations")

    return {
        "type": "chart",
        "ok": True,
        "title": f"Drive route map — {radius} mi radius",
        "chart_type": "coverage_drive_route",
        "plotly_json": fig.to_json(),
        "source_csv": result.get("source"),
    }


def build_coverage_map_artifacts(result: dict[str, Any]) -> list[dict]:
    """GeoJSON map: green = best, red = weak, blue = suggested."""
    if not result.get("ok"):
        return []

    features: list[dict] = []
    for i, row in enumerate(result.get("best_measured") or []):
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
            "properties": {
                "kind": "best",
                "rank": i + 1,
                "rf_score": row["rf_score"],
                "rsrp": row.get("rsrp"),
                "sinr": row.get("sinr"),
            },
        })
    for row in result.get("weak_zones") or []:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
            "properties": {"kind": "weak", "rf_score": row["rf_score"]},
        })
    for row in result.get("suggested_verify") or []:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
            "properties": {
                "kind": "suggested",
                "predicted_sinr": row.get("predicted_sinr_db"),
                "confidence": row.get("confidence"),
            },
        })
    c = result["center"]
    features.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [c["lon"], c["lat"]]},
        "properties": {"kind": "center", "radius_miles": c["radius_miles"]},
    })

    artifacts: list[dict] = [{
        "type": "map",
        "ok": True,
        "title": f"Coverage optimizer — {c['radius_miles']} mi radius",
        "geojson": {"type": "FeatureCollection", "features": features},
        "point_count": len(features),
        "source_csv": result.get("source"),
    }]

    from .coverage_google_map import build_coverage_google_map_artifact

    google_map = build_coverage_google_map_artifact(result)
    if google_map:
        artifacts.insert(0, google_map)

    # Plotly fallback when Google Maps API key not set on frontend
    drive_chart = build_coverage_drive_route_chart(result)
    if drive_chart:
        artifacts.append(drive_chart)

    return artifacts
