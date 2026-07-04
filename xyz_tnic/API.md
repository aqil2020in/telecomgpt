# TNIC API Reference

Base URL: `/api/v1`  
Interactive docs: `/docs` (Swagger) · `/redoc`

---

## Health

### `GET /api/v1/health`

Returns service status and dependency checks.

**Response**
```json
{
  "status": "ok",
  "app": "XYZ Telecom Network Intelligence Copilot",
  "version": "1.0.0",
  "postgres": "ok",
  "chroma": "ok",
  "openai": "configured"
}
```

---

## Root Cause Analysis

### `POST /api/v1/analyze/rca`

Run the Master RCA Orchestrator across specialist agents.

**Request body**
| Field | Type | Description |
|-------|------|-------------|
| `query` | string | Natural-language fault description |
| `issue_type` | string? | Force domain: `handover`, `call_drop`, `throughput`, … |
| `kpis` | KPIInput | Optional counter snapshot |
| `complaint_text` | string? | Customer complaint text |
| `include_rag` | bool | Include knowledge base context (default true) |
| `generate_report` | bool | Generate OpenAI narrative report (default false) |

**KPIInput fields:** `cell_id`, `ss_rsrp`, `ss_sinr`, `cqi`, `bler`, `throughput_mbps`, `ho_success_rate`, `ho_prep_fail_rate`, `rach_success_rate`, `call_drop_rate`, `rlf_rate`, `beam_failure_ratio`, `latency_ms`, `upf_latency_ms`, …

**Response:** `RCAResponse` with `issue_type`, `agents_run`, `findings`, `probable_root_causes`, `recommended_actions`, `validation_checklist`, `health_score`, `knowledge_graph`, `rag_context`, `narrative_report`.

### Domain-specific shortcuts

| Endpoint | Forces issue type |
|----------|-------------------|
| `POST /api/v1/analyze/handover` | handover |
| `POST /api/v1/analyze/call-drop` | call_drop |
| `POST /api/v1/analyze/throughput` | throughput |
| `POST /api/v1/analyze/rach` | rach |
| `POST /api/v1/analyze/latency` | latency |
| `POST /api/v1/analyze/beamforming` | beamforming |

---

## RF Coverage (`/coverage`)

Geospatial drive-test analysis using `enhanced_geospatial_rf_dataset.csv`.

### `POST /api/v1/analyze-coverage`

Run RF Coverage Agent for a cell. Writes `coverage_summary.json` and `coverage_hotspots.csv` when `write_outputs=true`.

**Request**
```json
{
  "cell_id": "XYZ401",
  "query": "",
  "radius_miles": 3.0,
  "write_outputs": true
}
```

**Response fields:** `cell_id`, `coverage_score`, `primary_issue`, `secondary_issue`, `confidence`, `recommendation`, `issue_counts`, `metrics`, `impacts`.

### `GET /api/v1/coverage-summary`

Return per-cell summary (`?cell_id=XYZ401`) or full multi-cell JSON artifact.

### `GET /api/v1/coverage-hotspots`

Return geospatial hotspot records. Query params: `cell_id`, `limit` (default 100).

**Hotspot types:** `coverage_hole`, `weak_coverage`, `interference`, `low_sinr`, `high_bler`, `low_throughput`, `latency_hotspot`, `beam_coverage_gap`, `cell_edge`.

---

## Health scoring

### `POST /api/v1/health-score/cell`

Compute 8-dimension health score for a cell.

**Request**
```json
{
  "cell_id": "43211",
  "kpis": { "ss_sinr": 4.2, "call_drop_rate": 3.2, "ho_success_rate": 91.0 }
}
```

**Response**
```json
{
  "cell_id": "43211",
  "overall_score": 62.3,
  "grade": "C",
  "dimensions": { "rf": 55.0, "mobility": 50.0, ... },
  "alerts": ["Mobility health critical — review HO KPIs"]
}
```

---

## PM counters

### `POST /api/v1/pm/ingest`

Upload PM counter CSV (`cell_id`, `counter_name`, `counter_value`, `period_start`).

**Response:** rows ingested, cells, KPI summary, validation issues.

### `GET /api/v1/pm/cell/{cell_id}/kpis`

Return aggregated KPIs from bundled `data/pm_counters.csv`.

---

## Incidents

### `GET /api/v1/incidents`

List sample telecom incidents. Optional query: `?issue_type=call_drop`.

### `GET /api/v1/incidents/{incident_id}`

Return single incident (e.g. `INC-2026-001`).

---

## Telecom datasets (`/datasets`)

Bundled CSV datasets drive KPI calculation for all RCA agents.

| File | Description |
|------|-------------|
| `pm_counters.csv` | Hourly PM counters per cell (HO, RACH, throughput, CQI) |
| `handover_events.csv` | UE handover events with RSRP/SINR and failure type |
| `rlf_events.csv` | Radio link failure events with cause |
| `rach_events.csv` | RACH MSG1–MSG4 outcomes |
| `call_drop_events.csv` | Call drops by type (Mobility, Radio, Core, IMS) |
| `throughput_metrics.csv` | Throughput samples with CQI, PRB util, issue tag |
| `enhanced_geospatial_rf_dataset.csv` | Geospatial drive test — RSRP, SINR, beam, lat/lon (RF Coverage Agent) |

Set `TNIC_DATASETS_DIR` to override the dataset directory (default: `data/datasets/`).

### `GET /api/v1/datasets/summary`

Summaries for all six datasets (row counts, cells, category breakdowns).

### `GET /api/v1/datasets/{name}/summary`

Summary for one dataset (`pm_counters`, `handover_events`, …).

### `GET /api/v1/datasets/validate-all`

Run validation rules on all datasets.

### `GET /api/v1/datasets/kpis/{cell_id}`

Merged KPIs for a cell from all datasets (feeds RCA agents).

### `GET /api/v1/datasets/kpis`

Cluster KPI overview with worst cells by health score.

### `GET /api/v1/datasets/cells`

List all cell IDs across datasets.

---

## Orchestration map

| Issue type | Agents invoked |
|------------|----------------|
| call_drop | call_drop, rlf, handover, beamforming, core |
| throughput | throughput, beamforming, transport, pm |
| handover | handover, rlf, pm |
| rach | rach, beamforming, pm |
| latency | latency, transport, core |
| rlf | rlf, handover, call_drop, pm |
| rf_coverage | rf_coverage, rlf, handover, call_drop, rach, throughput, beamforming, complaint |
| complaint | complaint, handover, throughput, call_drop, rf_coverage |

**Coverage correlation:** When coverage issues are detected, `master_rca.py` adds cross-domain findings (Coverage Hole → HO Failure, RLF, Call Drops, RACH Failure, Throughput Degradation, Customer Complaints).

---

## Error responses

```json
{
  "ok": false,
  "error": "Human-readable message",
  "detail": {}
}
```

| Code | Meaning |
|------|---------|
| 400 | Ingestion / bad input |
| 404 | Resource not found |
| 422 | Validation error |
| 500 | RCA / internal error |

---

## Environment variables

See `.env.example`. Key variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | — | Narrative RCA reports |
| `TNIC_ENABLE_CHROMA` | `1` | Enable ChromaDB RAG |
| `DATABASE_URL` | SQLite | PostgreSQL in Docker/prod |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
