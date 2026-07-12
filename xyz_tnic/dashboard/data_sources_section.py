"""Data sources info box — sidebar page → CSV file → row count for management demos."""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import streamlit as st

from tnic.datasets.registry import DATASET_FILES, DatasetName, datasets_dir

# Sidebar page → primary CSV(s) → loader
PAGE_SOURCES: list[dict[str, Any]] = [
    {"page": "app (home)", "icon": "📡", "files": ["pm_counters.csv", "+ merged KPIs"], "loader": None},
    {"page": "Handover", "icon": "🔄", "files": ["handover_events_enriched.csv"], "loader": "handover"},
    {"page": "RLF", "icon": "📶", "files": ["rlf_events.csv"], "loader": "rlf"},
    {"page": "Call Drops", "icon": "📵", "files": ["call_drop_events.csv"], "loader": "call_drop"},
    {"page": "RACH", "icon": "📶", "files": ["rach_events.csv"], "loader": "rach"},
    {"page": "Throughput", "icon": "⚡", "files": ["throughput_metrics.csv", "pm_counters.csv"], "loader": "throughput"},
    {"page": "Beamforming", "icon": "📡", "files": ["pm_counters.csv"], "loader": "pm"},
    {"page": "RCA Report", "icon": "🔍", "files": ["all datasets (merged)"], "loader": "all"},
    {"page": "RF Coverage Map", "icon": "🗺️", "files": ["enhanced_geospatial_rf_dataset.csv"], "loader": "rf_geo"},
    {"page": "VoNR", "icon": "📞", "files": ["vonr_sessions.csv"], "loader": "vonr"},
    {"page": "ANR", "icon": "🔗", "files": ["anr_events.csv", "neighbor_relations.csv"], "loader": "anr"},
    {"page": "Config Audit", "icon": "⚙️", "files": ["cell_configuration.csv"], "loader": "config"},
    {"page": "gNB Syslog", "icon": "📋", "files": ["gnb_syslog.csv"], "loader": "gnb_syslog"},
    {"page": "Alarm Correlation", "icon": "🚨", "files": ["alarm_events.csv"], "loader": "alarm"},
    {"page": "Assurance Hub", "icon": "🛡️", "files": ["assurance datasets"], "loader": "assurance"},
    {"page": "UE Protocol", "icon": "📱", "files": ["ue_protocol_trace.csv"], "loader": "ue_protocol"},
    {"page": "Upload", "icon": "📤", "files": ["user uploads → data/uploads/"], "loader": None},
    {"page": "RF Coverage", "icon": "📊", "files": ["enhanced_geospatial_rf_dataset.csv"], "loader": "rf_geo"},
]


def _count_loader(name: str) -> int | None:
    from agents.rf_coverage_agent import geospatial_dataset_path, load_geospatial_df
    from dashboard.dashboard_utils import _load_handover_enriched_df
    from tnic.datasets.loaders import (
        load_alarm_events,
        load_anr_events,
        load_call_drop_events,
        load_cell_configuration,
        load_gnb_syslog,
        load_pm_counters,
        load_rach_events,
        load_rlf_events,
        load_throughput_metrics,
        load_ue_protocol_trace,
        load_vonr_sessions,
    )

    loaders: dict[str, Callable[[], pd.DataFrame]] = {
        "handover": _load_handover_enriched_df,
        "rlf": load_rlf_events,
        "call_drop": load_call_drop_events,
        "rach": load_rach_events,
        "throughput": load_throughput_metrics,
        "pm": load_pm_counters,
        "vonr": load_vonr_sessions,
        "anr": load_anr_events,
        "config": load_cell_configuration,
        "gnb_syslog": load_gnb_syslog,
        "alarm": load_alarm_events,
        "ue_protocol": load_ue_protocol_trace,
        "rf_geo": lambda: load_geospatial_df(geospatial_dataset_path()),
    }
    fn = loaders.get(name)
    if not fn:
        return None
    try:
        return len(fn())
    except Exception:
        return None


def _count_file(filename: str) -> int | None:
    if filename.startswith("+") or "merged" in filename or "uploads" in filename:
        return None
    path = datasets_dir() / filename
    if not path.exists():
        return None
    try:
        return len(pd.read_csv(path))
    except Exception:
        return None


@st.cache_data(ttl=120, show_spinner=False)
def build_data_sources_table() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    ds_path = str(datasets_dir())

    for entry in PAGE_SOURCES:
        files = entry["files"]
        loader = entry.get("loader")
        row_counts: list[str] = []

        if loader == "all":
            total = sum(
                c for c in (
                    _count_loader("handover"),
                    _count_loader("rlf"),
                    _count_loader("pm"),
                ) if c is not None
            )
            row_counts.append(f"~{total:,}" if total else "—")
        elif loader == "assurance":
            parts = []
            for key in ("gnb_syslog", "config", "anr", "vonr", "alarm", "ue_protocol"):
                c = _count_loader(key)
                if c is not None:
                    parts.append(c)
            row_counts.append(f"{sum(parts):,}" if parts else "—")
        elif loader:
            c = _count_loader(loader)
            row_counts.append(f"{c:,}" if c is not None else "—")
        else:
            for f in files:
                c = _count_file(f)
                row_counts.append(f"{c:,}" if c is not None else "—")

        rows.append({
            "Page": f"{entry['icon']} {entry['page']}",
            "CSV file(s)": ", ".join(files),
            "Rows": " · ".join(row_counts) if row_counts else "—",
            "Dataset dir": ds_path,
        })

    return pd.DataFrame(rows)


def render_data_sources_section() -> None:
    """Render management demo data sources info box."""
    st.markdown(
        """
        <style>
        .ds-info {
            background: linear-gradient(135deg, #f0f9ff 0%, #f8fafc 100%);
            border: 1px solid #bae6fd; border-radius: 12px;
            padding: 1rem 1.1rem; margin: 0.5rem 0 1rem 0;
        }
        .ds-info h4 { margin: 0 0 0.35rem 0; color: #0c4a6e; font-size: 1rem; }
        .ds-info p { margin: 0; font-size: 0.82rem; color: #475569; line-height: 1.45; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### 📂 Data Sources")
    ds_dir = datasets_dir()
    st.markdown(
        f"""
        <div class="ds-info">
            <h4>Preloaded synthetic datasets (management reference)</h4>
            <p>
                Each sidebar page reads CSV files from <code>{ds_dir}</code>.
                KPIs are merged per cell (<strong>XYZ401–XYZ410</strong>).
                Upload page uses a separate path: <code>xyz_tnic/data/uploads/</code>.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df = build_data_sources_table()
    st.dataframe(
        df[["Page", "CSV file(s)", "Rows"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Page": st.column_config.TextColumn("Dashboard page", width="medium"),
            "CSV file(s)": st.column_config.TextColumn("Source file(s)", width="large"),
            "Rows": st.column_config.TextColumn("Row count", width="small"),
        },
    )

    # File inventory with exact counts
    with st.expander("Full CSV inventory (all files in dataset directory)"):
        inventory: list[dict[str, str | int]] = []
        for name, fname in sorted(DATASET_FILES.items(), key=lambda x: x[1]):
            path = ds_dir / fname
            if path.exists():
                try:
                    n = len(pd.read_csv(path))
                    inventory.append({"File": fname, "Rows": n, "Status": "✅ loaded"})
                except Exception as exc:
                    inventory.append({"File": fname, "Rows": 0, "Status": f"⚠ {exc}"})
            else:
                inventory.append({"File": fname, "Rows": 0, "Status": "— missing"})
        geo = ds_dir / "enhanced_geospatial_rf_dataset.csv"
        if geo.exists() and "enhanced_geospatial_rf_dataset.csv" not in [i["File"] for i in inventory]:
            inventory.append({
                "File": "enhanced_geospatial_rf_dataset.csv",
                "Rows": len(pd.read_csv(geo)),
                "Status": "✅ loaded",
            })
        st.dataframe(pd.DataFrame(inventory), use_container_width=True, hide_index=True)

    st.caption(
        "See GitHub: docs/TNIC_DASHBOARD_DATA_FLOW.md · "
        "Restart Streamlit after replacing CSVs to refresh counts."
    )
