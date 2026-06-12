"""RF map artifacts — GeoJSON + Plotly geo charts from drive-test CSV."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import plotly.express as px

from .csv_tools import detect_rf_columns, load_csv_path


def build_rf_map_artifacts(path: str, *, max_points: int = 500) -> list[dict]:
    df = load_csv_path(path)
    rf = detect_rf_columns(df)
    lat_col = rf.get("latitude")
    lon_col = rf.get("longitude")
    if not lat_col or not lon_col:
        return []

    rsrp_col = rf.get("rsrp") or rf.get("sinr")
    sample = df.dropna(subset=[lat_col, lon_col]).head(max_points)
    if sample.empty:
        return []

    artifacts: list[dict] = []

    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(row[lon_col]), float(row[lat_col])]},
                "properties": {
                    "rsrp": float(row[rsrp_col]) if rsrp_col and pd.notna(row.get(rsrp_col)) else None,
                },
            }
            for _, row in sample.iterrows()
            if pd.notna(row[lat_col]) and pd.notna(row[lon_col])
        ],
    }
    artifacts.append(
        {
            "type": "map",
            "ok": True,
            "title": f"RF map — {sample.iloc[0].get('Locality', path.split('/')[-1]) if 'Locality' in sample.columns else path.split(chr(92))[-1]}",
            "geojson": geojson,
            "point_count": len(geojson["features"]),
            "source_csv": path.split("\\")[-1].split("/")[-1],
        }
    )

    color = rsrp_col
    try:
        fig = px.scatter_geo(
            sample,
            lat=lat_col,
            lon=lon_col,
            color=color,
            hover_name=lat_col,
            title=f"RF coverage map ({len(sample)} points)",
            color_continuous_scale="RdYlGn_r" if color else None,
        )
        fig.update_layout(margin=dict(l=20, r=20, t=50, b=20), height=480)
        artifacts.append(
            {
                "type": "chart",
                "ok": True,
                "title": "RF geo scatter",
                "chart_type": "scatter_geo",
                "plotly_json": fig.to_json(),
                "source_csv": path.split("\\")[-1].split("/")[-1],
            }
        )
    except Exception:
        pass

    return artifacts


def artifacts_from_dataframe(df: pd.DataFrame, label: str = "upload") -> list[dict]:
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.gettempdir()) / f"telecomgpt_{label}.csv"
    df.to_csv(tmp, index=False)
    return build_rf_map_artifacts(str(tmp))
