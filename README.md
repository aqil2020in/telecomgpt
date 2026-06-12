# TelecomGPT

A domain-specific AI assistant for cellular/RF engineering with a **multi-agent orchestrator**:
planning, tool use, vector memory, RAG, analytics, and **PowerPoint report** generation.

## Architecture

See **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** for the full next-gen diagram (orchestrator, agents, memory, tools, PPT).

```
backend/                  FastAPI + multi-agent orchestrator
  app.py                  REST API (POST /ask, /api/ppt/generate, /api/tools)
  telecom_ai/
    orchestrator.py       Multi-agent LangGraph (supervisor → specialists → synthesizer)
    planning.py           Autonomous planner
    tools.py              Tool-use framework (KB, RAG, analytics, PPT)
    agents/specialists.py telecom_kb | research | analytics | presentation
    graph.py              Legacy keyword router (TELECOMGPT_MODE=legacy)
    core.py               TelecomAI facade
  memory/                 Session + vector memory (ChromaDB)
  ppt/                    PowerPoint report generator (python-pptx)
  data/
    telecom_master_db.json  NR/LTE band plans, CA/EN-DC/NR-DC combos, FCC lists, glossary
    devices/*.json          Per-device sheets incl. validated ca/endc/nrdc combo lists
  tools/
    arfcn_calculator.py     NR-ARFCN <-> frequency (TS 38.104 §5.4.2.1)
    gscn_calculator.py      GSCN <-> SSB frequency (TS 38.104 §5.4.3.1)
    throughput_calculator.py  NR peak data rate (TS 38.306 §4.1.2)
frontend/                 Next.js (pages router, TypeScript) minimal ask UI
analytics/                CSV + log analysis dashboard (Streamlit)
  app.py                  Interactive charts (line, bar, histogram, scatter, box)
  samples/                Example drive-test CSV and UE log
  backend/analytics/      Shared analytics engine (CSV, logs, Plotly charts)
```

## Analytics (CSV, logs, charts)

Interactive dashboard for drive-test CSVs, KPI exports, and UE/gNB logs.

```powershell
pip install -r analytics/requirements.txt
pip install -r backend/requirements.txt   # if using API endpoints too
streamlit run analytics/app.py            # http://localhost:8501
```

| Feature | What it does |
| --- | --- |
| **CSV tab** | Upload or load sample → preview, stats, null counts |
| **Charts** | Line, bar, histogram, scatter, box (Plotly) |
| **Log tab** | Parse INFO/WARN/ERROR/FATAL, top error patterns, level chart |
| **Samples** | `analytics/samples/drive_test.csv`, `ue_log.txt` |

**REST API** (when backend is running):

| Endpoint | Input | Output |
| --- | --- | --- |
| `POST /api/analytics/csv/summary` | CSV file | Row/column stats + preview |
| `POST /api/analytics/csv/chart` | CSV + chart_type, x, y | Plotly JSON |
| `POST /api/analytics/logs/analyze` | `.log` / `.txt` | Level counts + top errors + chart |
| `GET /api/analytics/kaggle/datasets` | — | Curated 5G Kaggle catalog + download status |
| `GET /api/analytics/kaggle/local` | — | List downloaded CSV files under `backend/data/kaggle/` |

Try in Swagger: http://localhost:8000/docs

### Kaggle 5G datasets

Curated datasets from [Kaggle search: 5g](https://www.kaggle.com/datasets?search=5g) are listed in
`backend/data/kaggle/datasets.json`. Download them locally for analytics / ML experiments.

**One-time setup**

1. Create a Kaggle account and accept each dataset’s license on its Kaggle page.
2. Install the CLI: `pip install kaggle`
3. Authenticate (pick one):
   - **OAuth (recommended):** `kaggle auth login`
   - **API token:** [Kaggle Settings → API](https://www.kaggle.com/settings) → Generate New Token → save as `%USERPROFILE%\.kaggle\kaggle.json`

**Download**

```powershell
cd backend
python scripts/download_kaggle.py list
python scripts/download_kaggle.py download --all
# or: python scripts/download_kaggle.py download srikumarnayak/5g-network-kpi-dataset
```

Files land in `backend/data/kaggle/<dataset-name>/`. CSV summaries auto-detect RF columns (RSRP, lat/lon, throughput, etc.).

**Included datasets**

| Dataset | Use case |
| --- | --- |
| [5G Network KPI Dataset](https://www.kaggle.com/datasets/srikumarnayak/5g-network-kpi-dataset) | KPI trends, throughput, latency-style ML |
| [Wireless Network Slicing](https://www.kaggle.com/datasets/ziya07/wireless-network-slicing-dataset) | Slicing, RSRP-based QoS / handover |
| [ITU AI/ML in 5G (LLM pairs)](https://www.kaggle.com/datasets/adamlogman/llms-for-telecom-networks-by-itu-aiml-in-5g) | Telecom Q&A fine-tuning / eval |
| [Cellular Network Analysis](https://www.kaggle.com/datasets/suraj520/cellular-network-analysis-dataset) | Signal strength, throughput, RF features |

For GPS drive-test mapping, see also **Vienna 4G/5G (Zenodo)** and **Berlin V2X (IEEE DataPort)** in the catalog JSON.

### RAG (ShareTechnote + 3GPP references)

Open-ended answers are grounded with **retrieved excerpts** from ingested pages
(ShareTechnote 5G handbook, selected topics, 3GPP 5G overview). Chunks ship in
`backend/data/rag/chunks.json` (~80 pages, BM25 search).

Refresh the index locally:

```bash
python backend/scripts/ingest_rag.py
# or POST /api/rag/reindex (dev — re-fetches the web)
```

With `OPENAI_API_KEY` set, the LLM synthesizes KB + RAG excerpts and appends
**Sources** URLs. Without a key, RAG excerpts are returned directly for LLM-routed queries.

## Quick start

### 1. Backend (Python 3.10+)

```bash
pip install -r requirements.txt
cd backend
uvicorn app:app --host 0.0.0.0 --port 8000
```

Interactive API docs at http://127.0.0.1:8000/docs. Add `--reload` during development.

### 2. Frontend (Node 18+)

```bash
cd frontend
npm install
npm run dev                  # serves http://localhost:3000
```

The page calls the backend at `NEXT_PUBLIC_API_URL` (defaults to
`https://telecomgpt.onrender.com`). For local dev, set
`NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local`. CORS is
enabled on the FastAPI app.

### Deploy backend (Render)

Connect the GitHub repo on [Render](https://render.com). Set **Root Directory** to
`backend`, then:

- **Build:** `pip install -r requirements.txt`
- **Start:** `uvicorn app:app --host 0.0.0.0 --port $PORT`
- **Health check:** `/api/health`

Or deploy with the included `render.yaml` blueprint (uses `rootDir: backend`).

**Live API:** https://telecomgpt.onrender.com

#### Local LLM with Ollama (your PC)

Render cannot reach Ollama on your home PC. Use Ollama when running the **backend
locally**:

```powershell
# 1. Install and start Ollama — https://ollama.com
ollama pull llama3.1

# 2. Run the backend with Ollama enabled
cd backend
$env:TELECOMGPT_LLM = "ollama"
$env:OLLAMA_MODEL = "llama3.1:latest"   # must match `ollama list` on your PC
$env:OLLAMA_BASE_URL = "http://localhost:11434/v1"  # optional
uvicorn app:app --host 0.0.0.0 --port 8000

# 3. Point the frontend at localhost
cd ../frontend
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
npm run dev
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `TELECOMGPT_LLM` | `auto` | `ollama`, `openai`, or `auto` (try Ollama, then OpenAI) |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama OpenAI-compatible endpoint |
| `OLLAMA_MODEL` | `llama3.1:latest` | Model name from `ollama list` |
| `OPENAI_API_KEY` | — | Cloud fallback when `TELECOMGPT_LLM=openai` or `auto` |

To use Ollama with the **Vercel UI** + **local backend**, keep step 3 above
(`NEXT_PUBLIC_API_URL=http://localhost:8000`) — do not use the Render URL.

### Deploy frontend (Vercel)

Import `aqil2020in/telecomgpt` on [Vercel](https://vercel.com) and set:

| Setting | Value |
| --- | --- |
| **Root Directory** | `frontend` |
| **Framework** | Next.js (auto-detected) |
| **Build Command** | `npm run build` (default) |
| **Output** | `.next` (default) |

Optional environment variable (already the code default):

```
NEXT_PUBLIC_API_URL=https://telecomgpt.onrender.com
```

**Live UI (after deploy):** https://telecomgpt.vercel.app


| Query | What happens |
| --- | --- |
| `What is band n78?` | Band plan lookup from the master DB |
| `Does the S24 support n79?` | Device capability check |
| `Compare Pixel 9 vs iPhone 16` | Band/modem diff between two devices |
| `Does the iPhone 17 support carrier aggregation?` | Device CA/EN-DC/NR-DC combo summary |
| `Does the S23 support n77+n78 CA?` | Device-level combo validation |
| `Is carrier aggregation n41-n71 supported?` | Network-level CA combo validation |
| `Can I run EN-DC with b66+n77?` | EN-DC combo validation |
| `Is n77 FCC licensed?` | FCC category (licensed/unlicensed/mmWave) |
| `What FCC US bands exist for NR?` | US regulatory band overview |
| `ARFCN 632448` | NR-ARFCN → 3486.72 MHz (TS 38.104) |
| `Convert 3500 MHz to ARFCN` | Frequency → nearest raster point |
| `GSCN 7880` | SSB reference frequency lookup |
| `Max throughput 100 MHz 4 layers 256QAM` | TS 38.306 peak-rate formula |
| `What is DSS?` | Glossary definition |

## CLI usage of the calculators

The tools are standalone:

```bash
python backend/tools/arfcn_calculator.py 632448
python backend/tools/gscn_calculator.py 7880
python backend/tools/throughput_calculator.py
```

## API

| Method | Endpoint | Body | Returns |
| --- | --- | --- | --- |
| POST | `/ask` | `{"query": "...", "trace": false}` | `{"answer": "..."}` or with `"trace": true` also `"intent"` and `"steps"` |
| GET | `/api/devices` | — | Device summaries |
| GET | `/api/bands` | — | NR + LTE band plans |
| GET | `/api/health` | — | Liveness probe |

## Notes

- Device band lists are representative of US/international variants and are
  intended for demonstration; verify against FCC/operator certification data
  before engineering use.
- The routing layer is deterministic and traceable: every numeric answer cites
  the 3GPP clause used to compute it.
- To enable the LLM fallback for open-ended questions:
  1. Create an [OpenAI API key](https://platform.openai.com/api-keys)
  2. On **Render** → **telecomgpt** → **Environment** → add `OPENAI_API_KEY`
  3. Optional: `TELECOMGPT_MODEL` (default `gpt-4o-mini`)
  4. **Manual Deploy** to pick up the variable
- Without `OPENAI_API_KEY`, TelecomGPT answers from the built-in glossary, bands,
  devices, and calculators; unknown terms get ShareTechnote handbook links.
- `python backend/smoke_test.py` exercises all five routing branches.
