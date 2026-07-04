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

## Orchestration map

| Issue type | Agents invoked |
|------------|----------------|
| call_drop | call_drop, rlf, handover, beamforming, core |
| throughput | throughput, beamforming, transport, pm |
| handover | handover, rlf, pm |
| rach | rach, beamforming, pm |
| latency | latency, transport, core |
| rlf | rlf, handover, call_drop, pm |

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
