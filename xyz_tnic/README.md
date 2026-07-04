# XYZ Telecom Network Intelligence Copilot (TNIC)

Production-style **5G Root Cause Analysis (RCA) AI platform** for XYZ Telecom — built from the [Cursor AI Implementation Blueprint](https://pradeep-dhote9.medium.com/building-an-ai-powered-rca-assistant-for-5g-network-issues-call-drops-throughput-rach-4013b634d7ea).

**Stack:** Python · FastAPI · OpenAI · ChromaDB · PostgreSQL · Streamlit · Render

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Streamlit Dashboard (Operations / Engineering / Executive)      │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP
┌────────────────────────────▼────────────────────────────────────┐
│  FastAPI  /api/v1                                               │
│  ├── /health          ├── /analyze/rca                          │
│  ├── /analyze/handover├── /analyze/throughput                   │
│  ├── /analyze/rach    ├── /health-score/cell                    │
│  └── /pm/ingest       └── ...                                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Master RCA Orchestrator                                        │
│  complaint → issue detection → multi-agent run → knowledge graph│
└─────┬───────────────┬────────────────┬────────────────────────┘
      │               │                │
┌─────▼─────┐  ┌──────▼──────┐  ┌─────▼─────┐  ┌────────────────┐
│ 12 Agents │  │ Rule Engines│  │ RAG/Chroma│  │ OpenAI Report  │
│ HO, RLF,  │  │ HO/RLF/Tput │  │ playbooks │  │ (optional)     │
│ Tput, ... │  │ RACH/Beam/  │  │           │  │                │
│           │  │ Latency     │  │           │  │                │
└───────────┘  └─────────────┘  └───────────┘  └────────────────┘
      │               │                │
┌─────▼───────────────▼────────────────▼──────────────────────────┐
│  PostgreSQL (PM counters, incidents, RCA reports)                 │
└───────────────────────────────────────────────────────────────────┘
```

### Roadmap phases (per blueprint)

| Phase | Capability | Status |
|-------|------------|--------|
| **1** | Deterministic rule engines | ✅ Implemented |
| **2** | RAG over playbooks | ✅ ChromaDB + JSON fallback |
| **3** | OpenAI LLM narrator | ✅ Optional report generator |
| **4** | Predictive ML | 🔜 Future |

---

## Folder Structure

```
xyz_tnic/
├── app/
│   ├── main.py                 # FastAPI entry + lifespan
│   ├── config.py               # pydantic-settings (env)
│   ├── logging_config.py       # Structured logging
│   ├── api/routes/
│   │   ├── health.py           # /health
│   │   └── analyze.py          # RCA, HO, RACH, PM ingest
│   ├── agents/
│   │   ├── base.py             # BaseAgent ABC
│   │   └── specialists.py      # 12 specialist agents
│   ├── rules/
│   │   ├── engine.py           # RuleDefinition + RuleEngine
│   │   ├── ho_rules.py         # HO: prep/exec/early/late/ping-pong
│   │   ├── rlf_rules.py        # RLF: coverage, interference, T310
│   │   ├── call_drop_rules.py  # Radio/mobility/core/IMS/transport
│   │   ├── throughput_rules.py # CQI, BLER, MCS, congestion, backhaul
│   │   ├── rach_rules.py       # MSG1-4, PRACH, access delay, beam
│   │   ├── beamforming_rules.py# Overload, imbalance, coverage, health
│   │   └── latency_rules.py    # Air, Xn, N2, CU/DU, UPF, N6
│   ├── orchestrator/
│   │   ├── rca_orchestrator.py # Master RCA — multi-agent coordination
│   │   └── knowledge_graph.py  # complaint→KPI→fault→RCA→action
│   ├── rag/
│   │   └── retriever.py        # ChromaDB + token-overlap fallback
│   ├── services/
│   │   ├── pm_ingestion.py     # PM CSV ingest + counter validation
│   │   ├── health_scoring.py   # 8-dimension cell health score
│   │   └── report_generator.py # OpenAI + template RCA reports
│   ├── db/
│   │   ├── session.py          # SQLAlchemy models + init
│   │   └── schema.sql          # PostgreSQL DDL reference
│   └── models/
│       └── schemas.py          # Pydantic request/response models
├── dashboard/
│   └── streamlit_app.py        # Ops / Engineering / Executive UI
├── data/
│   ├── knowledge/              # RAG seed documents
│   └── samples/                # PM counters, cell KPIs, complaints
├── tests/                      # pytest unit + API tests
├── Dockerfile
├── docker-compose.yml          # Postgres + API local stack
├── render.yaml                 # Render deployment blueprint
├── requirements.txt
└── .env.example
```

---

## Module Guide

### `app/config.py`
Loads all settings from environment / `.env`. Supports SQLite fallback for local dev and test (`APP_ENV=test`).

### `app/rules/*`
**Phase 1 core.** Each file defines telecom-specific rules as `RuleDefinition` objects with:
- KPI threshold conditions
- Probable cause text
- Confidence score (0–1)
- Recommended actions

Rules are deterministic — no LLM required.

### `app/agents/specialists.py`
Thin wrappers that invoke rule engines. Includes:
- **HO, RLF, Call Drop, Throughput, RACH, Beamforming, Latency** agents
- **PM Agent** — counter consistency validation
- **Transport / Core** agents — backhaul and 5GC checks
- **Complaint Agent** — triages customer tickets to issue domain

### `app/orchestrator/rca_orchestrator.py`
**Master RCA Agent.** For each request:
1. Detects issue type from query/complaint keywords
2. Runs 2–4 specialist agents (orchestration map)
3. Merges findings, sorts by confidence
4. Builds knowledge graph
5. Computes health score
6. Optionally generates OpenAI narrative report

### `app/rag/retriever.py`
**Phase 2.** Indexes troubleshooting playbooks into ChromaDB. Falls back to token-overlap search if Chroma unavailable.

### `app/services/pm_ingestion.py`
Ingests vendor PM CSV (`cell_id`, `counter_name`, `counter_value`) into PostgreSQL. Normalizes counter aliases (`qdrop` → `call_drop_rate`). Validates counter consistency.

### `app/services/health_scoring.py`
Weighted 8-dimension score: RF, coverage, throughput, mobility, access, reliability, latency, beam. Returns grade A–D and alerts.

### `app/services/report_generator.py`
**Phase 3.** OpenAI GPT narrative when `OPENAI_API_KEY` set; otherwise structured template report.

### `dashboard/streamlit_app.py`
Three views:
- **Operations** — cell KPI table + charts
- **Engineering RCA** — interactive RCA with API call
- **Executive** — network-wide health summary

---

## Quick Start (Local)

```bash
cd xyz_tnic
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set OPENAI_API_KEY optionally

# Option A: SQLite (no Postgres)
export APP_ENV=development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Option B: Docker Compose (Postgres + API)
docker compose up --build
```

**API docs:** http://localhost:8000/docs

**Streamlit:**
```bash
STREAMLIT_API_URL=http://localhost:8000 streamlit run dashboard/streamlit_app.py
```

---

## Example API Calls

```bash
# Health
curl http://localhost:8000/api/v1/health

# RCA — low throughput
curl -X POST http://localhost:8000/api/v1/analyze/rca \
  -H "Content-Type: application/json" \
  -d '{
    "query": "RCA low throughput cell 43211",
    "issue_type": "throughput",
    "kpis": {"cqi": 7.3, "bler": 15.2, "throughput_mbps": 28.5, "ri": 1.1},
    "include_rag": true,
    "generate_report": true
  }'

# Handover analysis
curl -X POST http://localhost:8000/api/v1/analyze/handover \
  -H "Content-Type: application/json" \
  -d '{"query": "HO prep failure", "kpis": {"ho_prep_fail_rate": 7.0, "ho_success_rate": 91.0}}'

# Cell health score
curl -X POST http://localhost:8000/api/v1/health-score/cell \
  -H "Content-Type: application/json" \
  -d '{"cell_id": "43211", "kpis": {"ss_sinr": 4.2, "call_drop_rate": 3.2}}'

# PM counter ingest
curl -X POST http://localhost:8000/api/v1/pm/ingest \
  -F "file=@data/samples/pm_counters_sample.csv"
```

---

## Deploy to Render

1. Push repo to GitHub
2. Create **Web Service** from `xyz_tnic/Dockerfile`
3. Create **PostgreSQL** database on Render
4. Set environment variables:
   - `DATABASE_URL` (from Render Postgres)
   - `OPENAI_API_KEY`
   - `CHROMA_PERSIST_DIR=/app/data/chroma`
5. Use `render.yaml` for blueprint deploy

ChromaDB persists to disk on Render — use a persistent disk mount for production.

---

## Tests

```bash
cd xyz_tnic
APP_ENV=test pytest tests/ -v

# Or run individually:
python tests/test_rules.py
python tests/test_orchestrator.py
python tests/test_api.py
python tests/test_health_scoring.py
```

---

## Relationship to TelecomGPT

This is a **standalone XYZ platform application** in `xyz_tnic/`. The main TelecomGPT repo (`backend/`) remains the multi-agent web copilot. TNIC is designed for:
- Operator NOC/SOC integration
- PM counter pipelines
- Structured RCA with confidence scoring
- Executive health dashboards

You can later bridge TNIC APIs into TelecomGPT's `fault_analysis` agent.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `OPENAI_API_KEY` | OpenAI API key for narrative reports |
| `OPENAI_MODEL` | Default `gpt-4o-mini` |
| `CHROMA_PERSIST_DIR` | ChromaDB storage path |
| `ENABLE_OPENAI_REPORTS` | `1` to enable LLM reports |
| `ENABLE_CHROMA` | `1` to enable vector RAG |
| `APP_ENV` | `development` / `test` / `production` |

---

## License

Internal XYZ Telecom learning / demo project.
