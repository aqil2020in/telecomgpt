# XYZ Telecom Network Intelligence Copilot (TNIC)

Production-quality multi-agent **5G Root Cause Analysis (RCA)** platform for telecom network operations.

Python 3.12 · FastAPI · OpenAI · ChromaDB · PostgreSQL · Streamlit · Docker · Render

---

## Features

| Component | Description |
|-----------|-------------|
| **13 specialist agents** | Handover, RLF, Call Drop, Throughput, RACH, Beamforming, Latency, **RF Coverage**, PM Validation, Transport, Core, Complaint + Master Orchestrator |
| **Rule engines** | KPI threshold rules per domain (3GPP-aligned counters) |
| **Health score engine** | 8-dimension weighted cell health (A–D grade) |
| **RAG knowledge base** | Markdown playbooks + JSON guides, ChromaDB with BM25 fallback |
| **OpenAI reports** | Narrative RCA when `OPENAI_API_KEY` is set |
| **PM ingestion** | CSV counter ingest + KPI validation |
| **Incident library** | Sample telecom incident dataset |
| **Streamlit dashboard** | RCA, health, PM, incidents, **RF Coverage Plotly maps** |
| **REST API** | Full `/api/v1` surface with OpenAPI docs |

---

## Folder structure

```
xyz_tnic/
├── agents/                     # RF Coverage Agent (geospatial rules)
│   └── rf_coverage_agent.py
├── tnic/                       # Python package
│   ├── main.py                 # FastAPI app entrypoint
│   ├── config.py               # Settings (.env)
│   ├── exceptions.py           # Error types + handlers
│   ├── logging_config.py       # Structured logging
│   ├── agents/
│   │   ├── base.py             # BaseAgent + kpi_to_dict
│   │   ├── rf_coverage_agent.py # Re-export from agents/
│   │   └── specialists.py      # 13 agents + AGENT_REGISTRY
│   ├── orchestrator/
│   │   ├── rca_orchestrator.py # MasterRCAOrchestrator
│   │   ├── master_rca.py       # Coverage correlation (HO/RLF/drops/RACH/TP)
│   │   └── knowledge_graph.py  # RCA knowledge graph
│   ├── rules/                  # Per-domain rule engines
│   ├── services/
│   │   ├── health_scoring.py   # Cell health engine
│   │   ├── pm_ingestion.py     # PM CSV ingest
│   │   ├── report_generator.py # OpenAI + template RCA
│   │   └── incidents.py        # Incident CSV loader
│   ├── datasets/               # Loaders, validation, KPI merge service
│   ├── rag/retriever.py        # ChromaDB + fallback search
│   ├── models/schemas.py       # Pydantic models
│   ├── api/routes/             # FastAPI routers (analyze, coverage, datasets, …)
│   └── db/                     # SQLAlchemy + schema.sql
├── dashboard/
│   ├── app.py                  # Executive summary home
│   └── pages/                  # Handover, RLF, Call Drops, RACH, Throughput, Beamforming, RCA, RF Coverage
├── scripts/ingest_chroma.py    # ChromaDB ingestion CLI
├── data/
│   ├── pm_counters.csv         # Sample PM counters
│   ├── incidents.csv           # Sample telecom incidents
│   ├── datasets/               # Telecom RCA datasets (6 CSVs + geospatial RF)
│   └── knowledge/              # RCA markdown playbooks
├── datasets/                   # Canonical dataset copies (repo root symlink target)
├── tests/                      # pytest suite
├── Dockerfile
├── docker-compose.yml
├── render.yaml
├── requirements.txt
├── .env.example
├── API.md
└── README.md
```

---

## Quick start (local)

```bash
cd xyz_tnic
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Ingest knowledge base
python scripts/ingest_chroma.py

# Start API
uvicorn tnic.main:app --reload --port 8000

# Start dashboard (separate terminal)
streamlit run dashboard/app.py
```

- API docs: http://localhost:8000/docs  
- Health: http://localhost:8000/api/v1/health  
- Dashboard: http://localhost:8501  

---

## Docker

```bash
cd xyz_tnic
cp .env.example .env
docker compose up --build
```

Services: `api` (8000), `dashboard` (8501), `postgres` (5432).

---

## Render deployment

Use `render.yaml` in this directory. Set `OPENAI_API_KEY` and optionally `DATABASE_URL` in the Render dashboard.

---

## Example API calls

```bash
# RCA
curl -X POST http://localhost:8000/api/v1/analyze/rca \
  -H "Content-Type: application/json" \
  -d '{"query":"Root cause call drop","kpis":{"ho_success_rate":91,"call_drop_rate":3.2}}'

# Cell health
curl -X POST http://localhost:8000/api/v1/health-score/cell \
  -H "Content-Type: application/json" \
  -d '{"cell_id":"43211","kpis":{"ss_sinr":4.2,"call_drop_rate":3.2}}'

# Incidents
curl http://localhost:8000/api/v1/incidents
```

See [API.md](./API.md) for full endpoint documentation.  
**Agent build guide:** [docs/RCA_AGENT_END_TO_END_HANDOVER.md](../docs/RCA_AGENT_END_TO_END_HANDOVER.md)

---

## Tests

```bash
cd xyz_tnic
pytest -v
```

---

## Integration with TelecomGPT

The same TNIC engine is also embedded in the main TelecomGPT repo at `backend/tnic/` and wired into `/ask` via `bridge.py`. This `xyz_tnic/` directory is the **standalone, deployable** project per the RCA Copilot blueprint.

---

## License

Internal XYZ Telecom engineering demo.
