# TNIC Dashboard — Data Preload & Sidebar Page Flow

**Audience:** NPI engineers, management demos, developers  
**Platform:** XYZ Telecom Network Intelligence Copilot (TNIC)  
**Last updated:** 2026-07-12 (demo cells section added)

**Related:** [RCA_AGENT_END_TO_END_HANDOVER.md](./RCA_AGENT_END_TO_END_HANDOVER.md) · [ARCHITECTURE.md](./ARCHITECTURE.md) · [TNIC_FULL_IMPLEMENTATION_OVERVIEW.md](./TNIC_FULL_IMPLEMENTATION_OVERVIEW.md) · [xyz_tnic/README.md](../xyz_tnic/README.md)

---

## Summary

The Streamlit sidebar pages (**app**, **Handover**, **RLF**, **Call Drops**, etc.) do **not** pull from a live OSS or Nokia network. They read **preloaded synthetic CSV files** from disk, aggregate KPIs in Python, and run rule-based RCA agents on demand.

There are two data paths:

1. **Preloaded demo datasets** — used by most sidebar pages (Handover, RLF, VoNR, …)
2. **User uploads** — used by **Upload** and **Dataset Upload & Agent Simulation** on the home page

---

## 1. How the sidebar is built

Streamlit **multipage** mode auto-discovers files under `xyz_tnic/dashboard/pages/`:

| Sidebar label | Source file |
|---------------|-------------|
| **app** | `dashboard/app.py` (home — executive summary + NPI sections) |
| **Handover** | `dashboard/pages/2_Handover.py` |
| **RLF** | `dashboard/pages/3_RLF.py` |
| **Call Drops** | `dashboard/pages/4_Call_Drops.py` |
| **RACH** | `dashboard/pages/5_RACH.py` |
| **Throughput** | `dashboard/pages/6_Throughput.py` |
| **Beamforming** | `dashboard/pages/7_Beamforming.py` |
| **RCA Report** | `dashboard/pages/8_RCA_Report.py` |
| **RF Coverage Map** | `dashboard/pages/9_RF_Coverage_Map.py` |
| **VoNR** | `dashboard/pages/10_VoNR.py` |
| **ANR** | `dashboard/pages/11_ANR.py` |
| **Config Audit** | `dashboard/pages/12_Config_Audit.py` |
| **gNB Syslog** | `dashboard/pages/13_gNB_Syslog.py` |
| **Alarm Correlation** | `dashboard/pages/14_Alarm_Correlation.py` |
| **Assurance Hub** | `dashboard/pages/15_Assurance_Hub.py` |
| **UE Protocol** | `dashboard/pages/16_UE_Protocol.py` |
| **Upload** | `dashboard/pages/17_Upload.py` |
| **RF Coverage** | `dashboard/pages/RF_Coverage.py` |

Each page is a standalone Python script. Opening **Handover** does not call a remote API by default — it loads CSVs in-process.

---

## 2. Where data lives on disk

### Primary dataset directory

```
/workspace/datasets/
```

Set via environment variable:

```bash
export TNIC_DATASETS_DIR=/workspace/datasets
```

### Fallback copy (bundled with xyz_tnic)

```
/workspace/xyz_tnic/data/datasets/
```

Resolution logic: `tnic/datasets/registry.py` → `datasets_dir()`

---

## 3. How demo cells XYZ401–XYZ410 were populated

The dashboard shows **10 demo cells** (`XYZ401` through `XYZ410`). You do **not** enter KPI or event data for each cell through the Streamlit UI. All ten cells are **preloaded in synthetic CSV files** that ship with the repository.

### What “input” means in the dashboard

| Your action in the UI | What happens under the hood |
|-----------------------|------------------------------|
| Select **Focus cell** / **Cell** in the dropdown | Filter preloaded CSV rows where `cell_id` (or `source_cell`) matches |
| Open Handover, RLF, VoNR, etc. | Load charts/tables from those filtered rows |
| Click through to agent findings | Rules run on KPIs merged from all CSVs for that cell |
| **Upload** page or home simulation | **Separate path** — one user file at a time; does not auto-fill all 10 cells |

For the standard management demo, **your only input is cell selection**.

### How the 10 cells got into the CSVs

Data was created **offline during development**, not typed into the dashboard:

```mermaid
flowchart LR
    GEN["Synthetic CSV generation\n+ remediation scripts"]
    GIT["Committed to GitHub\n/workspace/datasets/"]
    LOAD["Streamlit loaders\n@lru_cache"]
    UI["User selects XYZ401-410"]

    GEN --> GIT --> LOAD --> UI
```

1. **Initial datasets** — mobility, PM, and assurance CSVs added to `/workspace/datasets/` with a `cell_id` column on every row (values `XYZ401` … `XYZ410` where applicable).
2. **Remediation** — `scripts/remediate_datasets.py` fixes/enriches rows (HO failure mix, RLF causes, throughput issue labels, PM timestamp dedup). Copies synced to `xyz_tnic/data/datasets/` and `backend/data/datasets/`.
3. **Handover enrichment** — `scripts/enrich_handover_events.py` builds `handover_events_enriched.csv` (RSRP/SINR, failure stage, RCA scenarios) from raw `handover_events.csv`.

Regenerate after editing raw handover data:

```bash
python3 scripts/enrich_handover_events.py
python3 scripts/remediate_datasets.py   # optional full remediation pass
```

### Cell coverage per CSV file

Not every assurance file has all 10 cells; core mobility/PM files do. The KPI merge layer uses whatever is available per cell.

| CSV file | Cells present (typical) |
|----------|-------------------------|
| `pm_counters.csv` | **10** (XYZ401–410) |
| `handover_events.csv` / `handover_events_enriched.csv` | **10** |
| `rlf_events.csv` | **10** |
| `rach_events.csv` | **10** |
| `call_drop_events.csv` | **10** |
| `throughput_metrics.csv` | **10** |
| `vonr_sessions.csv` | 3 (subset) |
| `alarm_events.csv` | 3 (subset) |
| `gnb_syslog.csv` | 3 (subset) |
| `anr_events.csv` | 3 (subset) |
| `cell_configuration.csv` | 3 (subset) |
| `ue_protocol_trace.csv` | 1 (subset) |
| `enhanced_geospatial_rf_dataset.csv` | 3 (subset) |

Example row shape in `pm_counters.csv`:

```csv
timestamp,cell_id,ho_attempt,rach_attempt,dl_tp,ul_tp,cqi,ho_success,rach_success
2026-07-01 00:00:00,XYZ401,1941,401,447,41,8,1554,341
2026-07-01 00:00:00,XYZ402,1992,340,321,35,5,1675,272
```

Handover events use `source_cell` (or `cell_id`) the same way — each event row is tagged with one of the demo cells.

### How the dashboard discovers the cell list

Cells are **not** hard-coded in every page. They are collected from loaded CSVs:

```python
# tnic/datasets/kpi_service.py → list_cell_ids()
# Unions unique cell_id values across all loaders
```

The dropdown order is normalized to the demo range:

```python
# dashboard/dashboard_utils.py
DEMO_CELLS = [f"XYZ{i}" for i in range(401, 411)]  # XYZ401 … XYZ410
```

`dataset_cells()` returns `DEMO_CELLS` that exist in the CSVs, plus any extras found in data.

### What happens when you pick e.g. XYZ405

1. `compute_cell_kpis("XYZ405")` — merge PM, HO, RLF, RACH, drops, throughput, assurance for that cell
2. `handover_df("XYZ405")` — filter handover events where `source_cell == "XYZ405"`
3. `run_agent("handover", "XYZ405")` — HO rules evaluate merged KPIs
4. Charts and tables show only rows for XYZ405

The same pattern applies to every cell in the dropdown — data is **already in the CSV**, filtered by your selection.

### Preloaded vs upload data (important)

| Path | Scope | Used by |
|------|-------|---------|
| **Preloaded CSVs** | All 10 cells (where present in each file) | Handover, RLF, VoNR, home KPIs, RCA Report |
| **User upload** | One upload session at a time | Upload page, Dataset Simulation on home |

Upload KPIs are **merged** with bundled cell KPIs for dynamic RCA but do **not** replace preloaded sidebar data unless you copy files into `datasets/`.

### How to add or change data for all 10 cells

| Goal | Action |
|------|--------|
| Edit demo data | Change CSVs under `/workspace/datasets/` (keep `cell_id` / `source_cell` column) |
| Refresh handover enrichment | `python3 scripts/enrich_handover_events.py` then restart Streamlit |
| Run remediation scripts | `python3 scripts/remediate_datasets.py` |
| Use real OSS exports later | Point `TNIC_DATASETS_DIR` at a folder of PM/FM/CM CSVs with the same schema |
| Per-session test file | Upload page — does not populate all 10 cells automatically |

---

## 4. CSV file → sidebar page mapping

| Sidebar page | Primary CSV file(s) | Loader function |
|--------------|---------------------|-----------------|
| **app** (home KPIs) | All datasets merged | `compute_cell_kpis()` |
| **Handover** | `handover_events.csv` → `handover_events_enriched.csv` | `load_handover_events_enriched()` |
| **RLF** | `rlf_events.csv` | `load_rlf_events()` |
| **Call Drops** | `call_drop_events.csv` | `load_call_drop_events()` |
| **RACH** | `rach_events.csv` | `load_rach_events()` |
| **Throughput** | `throughput_metrics.csv`, `pm_counters.csv` | `load_throughput_metrics()`, `load_pm_counters()` |
| **Beamforming** | PM/KPI-derived + synthetic beam profile | `synthesize_beam_metrics()` |
| **VoNR** | `vonr_sessions.csv` | `load_vonr_sessions()` |
| **ANR** | `anr_events.csv`, `neighbor_relations.csv` | `load_anr_events()`, `load_neighbor_relations()` |
| **Config Audit** | `cell_configuration.csv` | `load_cell_configuration()` |
| **gNB Syslog** | `gnb_syslog.csv` | `load_gnb_syslog()` |
| **Alarm Correlation** | `alarm_events.csv` | `load_alarm_events()` |
| **UE Protocol** | `ue_protocol_trace.csv` | `load_ue_protocol_trace()` |
| **RF Coverage** | `enhanced_geospatial_rf_dataset.csv` | `RFCoverageAgent` / geospatial loaders |
| **Upload** | User-provided files | `ingest_uploaded_bytes()` |

**Demo cells:** `XYZ401`–`XYZ410` (embedded in CSV generation).

Full registry: `tnic/datasets/registry.py` → `DATASET_FILES`

---

## 5. End-to-end flow (Handover example)

What you see on **Handover → XYZ401**:

### Charts and event table (raw events)

```
handover_events_enriched.csv
        ↓
load_handover_events_enriched()     ← tnic/datasets/loaders.py (@lru_cache)
        ↓
handover_df("XYZ401")               ← dashboard/dashboard_utils.py
        ↓
pages/2_Handover.py                 ← bar charts, scatter, dataframe
```

### Top metrics (HO success %, prep fail %, …)

```
All CSVs for cell XYZ401
        ↓
compute_cell_kpis("XYZ401")         ← tnic/datasets/kpi_service.py
        ↓
cell_kpis("XYZ401")                   ← dashboard/dashboard_utils.py
        ↓
st.metric(...)
```

`kpi_service.py` merges PM, handover, RLF, RACH, throughput, syslog, VoNR, alarms, and assurance sources into one KPI dictionary per cell.

### HO Agent findings (bottom of page)

```
cell_kpis + rule engine
        ↓
run_agent("handover", "XYZ401")       ← dashboard/dashboard_utils.py
        ↓
HOAgent.analyze() → findings + summary
```

The same pattern applies to **RLF**, **VoNR**, **UE Protocol**, etc.: `{domain}_df()` + `cell_kpis()` + `run_agent("{domain}", cell_id)`.

---

## 6. Key code modules

| Layer | Path | Role |
|-------|------|------|
| Page UI | `xyz_tnic/dashboard/pages/*.py` | Streamlit charts, metrics, tables |
| Dashboard helpers | `xyz_tnic/dashboard/dashboard_utils.py` | `handover_df()`, `cell_kpis()`, `run_agent()`, `run_rca()` |
| CSV loaders | `xyz_tnic/tnic/datasets/loaders.py` | `pd.read_csv()` with `@lru_cache` |
| Dataset registry | `xyz_tnic/tnic/datasets/registry.py` | File names, path resolution |
| KPI merge | `xyz_tnic/tnic/datasets/kpi_service.py` | Per-cell KPI aggregation |
| HO enrichment | `xyz_tnic/tnic/datasets/handover_enrichment.py` | Raw HO → 33-column RCA-ready dataset |
| Rule agents | `xyz_tnic/tnic/agents/specialists.py` | HOAgent, RLFAgent, VoNRAgent, … |
| Master RCA | `xyz_tnic/tnic/orchestrator/rca_orchestrator.py` | Multi-agent orchestration |

### Loader caching

Loaders use `@lru_cache(maxsize=1)` — each CSV is read **once per Streamlit process**. After editing CSVs on disk, **restart Streamlit** or call `clear_loader_cache()` from `loaders.py`.

### Handover enrichment

If `handover_events_enriched.csv` exists, it is used directly. Otherwise enrichment runs on the fly from raw `handover_events.csv`.

Regenerate enriched file:

```bash
python3 scripts/enrich_handover_events.py
```

Output: `datasets/handover_events_enriched.csv`

---

## 7. Two data ingestion paths

### Path A — Preloaded (default for sidebar pages)

1. Synthetic CSVs live under `/workspace/datasets/`
2. Streamlit starts → loaders read CSVs into memory
3. Each page filters by `cell_id` or `source_cell`
4. **No database insert at runtime**

### Path B — User upload (Upload page + home simulation)

1. User drops a file (csv, xlsx, txt, log, json, xml, zip)
2. `ingest_uploaded_bytes()` → `file_classifier.py` → `normalization_engine.py`
3. Events stored as JSONL under `xyz_tnic/data/uploads/<upload_id>/`
4. `ingest_and_run_rca()` / `run_dynamic_rca()` merges upload KPIs with bundled cell KPIs
5. Master RCA runs on combined evidence

**Note:** Upload data does **not** automatically replace preloaded CSVs for Handover/RLF pages unless you copy files into `datasets/` or change `TNIC_DATASETS_DIR`.

---

## 8. Architecture diagram

```mermaid
flowchart TB
    subgraph disk ["On disk"]
        CSV["/workspace/datasets/*.csv"]
        UP["xyz_tnic/data/uploads/"]
    end

    subgraph loaders ["tnic/datasets/loaders.py"]
        LHO["load_handover_events_enriched()"]
        LRLF["load_rlf_events()"]
        LPM["load_pm_counters()"]
    end

    subgraph kpi ["tnic/datasets/kpi_service.py"]
        MERGE["compute_cell_kpis(cell_id)"]
    end

    subgraph dash ["dashboard/"]
        UTIL["dashboard_utils.py"]
        PAGES["pages/2_Handover.py, 3_RLF.py, ..."]
        AGENTS["run_agent() → specialists"]
    end

    CSV --> LHO & LRLF & LPM
    LHO --> UTIL
    LRLF --> UTIL
    LPM --> MERGE
    LHO --> MERGE
    MERGE --> UTIL
    UTIL --> PAGES
    UTIL --> AGENTS
    UP --> AGENTS
```

---

## 9. Backend API (optional)

The FastAPI app exposes the same RCA engine over REST:

```bash
cd xyz_tnic
uvicorn tnic.main:app --host 0.0.0.0 --port 8000
```

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/analyze/rca` | Master RCA |
| `POST /api/v1/upload/rca` | Upload + classify + RCA |
| `GET /api/v1/datasets/summary` | Dataset summaries |

Streamlit sidebar pages **read CSVs directly** unless the Upload page is configured with an API base URL.

---

## 10. How to refresh or replace demo data

| Goal | Action |
|------|--------|
| Update handover events | Edit `datasets/handover_events.csv`, run `python3 scripts/enrich_handover_events.py`, restart Streamlit |
| Point at a different CSV folder | `export TNIC_DATASETS_DIR=/path/to/csvs` before starting Streamlit |
| Test upload workflow | Use sidebar **Upload** or home **Dataset Upload & Agent Simulation** |
| Clear in-memory cache | Restart Streamlit (or `clear_loader_cache()` in a Python shell) |
| Run full test suite | `cd xyz_tnic && pytest tests/test_handover_enrichment.py -q` |

---

## 11. Start commands

```bash
# TNIC Streamlit dashboard (sidebar pages)
cd xyz_tnic
export TNIC_DATASETS_DIR=/workspace/datasets
streamlit run dashboard/app.py --server.port 8501

# Optional: TNIC API
uvicorn tnic.main:app --host 0.0.0.0 --port 8000
```

---

## 12. Management demo talking points

- Demo cells **XYZ401–XYZ410** are **preloaded in CSV files** — the dropdown only selects a cell; data is not entered manually in the UI.
- Sidebar pages show **representative synthetic telecom data** — same structure as field logs and OSS exports.
- KPIs and charts come from **real CSV loaders and rule engines**, not hard-coded UI numbers.
- **Upload path** demonstrates the future workflow: classify → agents → Master RCA → recommendations.
- Replacing CSVs with real PM/FM/CM exports requires **adapter changes only** — the agent orchestration layer stays the same.
