"""Network KPI campaign analysis — partial RF datasets (no full drive-test trace)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .csv_tools import detect_rf_columns, load_csv_path
from .rf_kpi import evaluate_rf_kpis, format_kpi_report


def analyze_network_kpi(path: str, *, network_filter: str | None = None) -> dict[str, Any]:
    df = load_csv_path(path)
    rf = detect_rf_columns(df)

    if network_filter and "Network Type" in df.columns:
        mask = df["Network Type"].astype(str).str.contains(network_filter, case=False, na=False)
        df_f = df[mask].copy()
    else:
        df_f = df

    kpi = evaluate_rf_kpis(path)
    lines = [format_kpi_report(kpi)]

    rsrp_col = rf.get("rsrp")
    if rsrp_col and rsrp_col in df_f.columns:
        s = pd.to_numeric(df_f[rsrp_col], errors="coerce")
        lines.append(f"\n**Signal ({rsrp_col})** — mean {s.mean():.1f} dBm, min {s.min():.1f}, max {s.max():.1f}")

    dl = rf.get("throughput")
    ul = rf.get("throughput_ul")
    if dl and dl in df_f.columns:
        t = pd.to_numeric(df_f[dl], errors="coerce")
        lines.append(f"**DL throughput** — mean {t.mean():.1f} Mbps")
    if ul and ul in df_f.columns:
        t = pd.to_numeric(df_f[ul], errors="coerce")
        lines.append(f"**UL throughput** — mean {t.mean():.1f} Mbps")

    if "Dropped Connection" in df_f.columns:
        drops = df_f["Dropped Connection"]
        if drops.dtype == bool or drops.dtype == object:
            n_drop = int(drops.astype(str).str.lower().isin(("true", "1", "yes")).sum())
        else:
            n_drop = int(pd.to_numeric(drops, errors="coerce").fillna(0).astype(bool).sum())
        pct = round(100 * n_drop / max(len(df_f), 1), 2)
        lines.append(f"**Dropped connections:** {n_drop} / {len(df_f)} ({pct}%)")

    if "Handover Count" in df_f.columns:
        ho = pd.to_numeric(df_f["Handover Count"], errors="coerce")
        lines.append(f"**Handover count** — mean {ho.mean():.2f}, max {int(ho.max())}")

    band_col = rf.get("band") or ("Band" if "Band" in df_f.columns else None)
    band_stats: list[dict] = []
    if band_col and band_col in df_f.columns and rsrp_col:
        grp = df_f.groupby(band_col, dropna=False)
        for band, sub in grp:
            sig = pd.to_numeric(sub[rsrp_col], errors="coerce")
            row: dict[str, Any] = {"band": str(band), "samples": len(sub), "rsrp_mean": round(float(sig.mean()), 1)}
            if dl and dl in sub.columns:
                row["dl_mean_mbps"] = round(float(pd.to_numeric(sub[dl], errors="coerce").mean()), 1)
            band_stats.append(row)
        lines.append("\n**Per-band summary**")
        lines.append("| Band | Samples | RSRP mean | DL mean Mbps |")
        lines.append("|------|---------|-----------|--------------|")
        for b in sorted(band_stats, key=lambda x: -x["samples"])[:8]:
            lines.append(
                f"| {b['band']} | {b['samples']} | {b.get('rsrp_mean', '—')} | {b.get('dl_mean_mbps', '—')} |"
            )

    if network_filter:
        lines.insert(1, f"*Filter: Network Type contains `{network_filter}` ({len(df_f)} rows)*")

    return {
        "ok": True,
        "path": path,
        "rows": len(df),
        "filtered_rows": len(df_f),
        "band_stats": band_stats,
        "report": "\n".join(lines),
    }
