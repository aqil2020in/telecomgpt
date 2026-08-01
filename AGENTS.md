# AGENTS.md

## Cursor Cloud specific instructions

This monorepo contains **two related telecom-AI products** plus shared analytics tooling.
All Python components share a single virtualenv at `/workspace/.venv` (created by the
startup update script). Use `/workspace/.venv/bin/python`, `/workspace/.venv/bin/uvicorn`,
`/workspace/.venv/bin/streamlit`, etc. (or activate it). System `python3` is 3.12 and Node is v22.

### Products & services

| Product | Service | Default port | Start command (from repo root, venv on PATH) |
| --- | --- | --- | --- |
| TelecomGPT | Backend API (`backend/app.py`) | 8000 | `cd backend && /workspace/.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000` |
| TelecomGPT | Frontend (Next.js) | 3000 | `cd frontend && npm run dev` |
| TelecomGPT | Analytics dashboard (Streamlit) | 8501 | `cd analytics && /workspace/.venv/bin/streamlit run app.py --server.port 8501 --server.headless true` |
| XYZ TNIC | RCA API (`tnic.main:app`) | 8010* | `cd xyz_tnic && /workspace/.venv/bin/uvicorn tnic.main:app --host 0.0.0.0 --port 8010` |
| XYZ TNIC | Dashboard (Streamlit) | 8502* | `cd xyz_tnic && TNIC_API_URL=http://localhost:8010/api/v1 /workspace/.venv/bin/streamlit run dashboard/app.py --server.port 8502 --server.headless true` |

\* Both APIs default to port **8000**. Run TelecomGPT and TNIC on different ports if you
start them at the same time (above uses 8010/8502 for TNIC). The TNIC dashboard reads the
API location from `TNIC_API_URL` (default `http://localhost:8000/api/v1`), so point it at the
port the TNIC API is actually running on.

### Non-obvious setup caveats

- **Frontend API URL**: `NEXT_PUBLIC_API_URL` defaults to the hosted Render URL. For local dev
  it must point at the local backend — set `NEXT_PUBLIC_API_URL=http://localhost:8000` in
  `frontend/.env.local` (this file is gitignored).
- **XYZ TNIC `.env`**: copy `xyz_tnic/.env.example` to `xyz_tnic/.env` before running (gitignored).
- **XYZ TNIC RAG ingestion**: `xyz_tnic/data/chroma/` (gitignored) holds the ingested RAG
  collection. If it is missing, run `cd xyz_tnic && /workspace/.venv/bin/python scripts/ingest_chroma.py`
  once before starting the TNIC API. The retriever falls back to BM25 if the collection is absent.
- **OpenAI is optional**: without `OPENAI_API_KEY`, both products fall back to deterministic
  KB/rules/template answers. Set it only to test generative/synthesis output.
- **Database**: TNIC defaults to SQLite (`xyz_tnic/data/tnic_local.db`); PostgreSQL
  (`DATABASE_URL`) is optional/production-only.

### Local TNIC manager demo (no Render)

For management demos **without Render or OpenAI**:

```bash
./start.demo                 # macOS / Linux / Cloud Agent
# Windows: start.demo.cmd    # double-click (Git Bash or WSL)
```

One script starts the RCA dashboard and opens the desktop browser (or prints a Cursor Browser hint on Cloud Agent). Handover → XYZ401 → RCA Report. See `docs/DEMO_TNIC_LOCAL_MANAGER.md`.
Uses `xyz_tnic/requirements-dashboard.txt` (lightweight; no Chroma). Sidebar pages do not call Render.

### Cursor training

See `docs/CURSOR_REFERENCE.md` (one-page guide) and `docs/CURSOR_TRAINING.md` (tutorials and workshop) for Cursor best practices on this repo.

### Tests / lint

- XYZ TNIC test suite: `cd xyz_tnic && /workspace/.venv/bin/python -m pytest` (100 tests).
- TelecomGPT backend smoke test: `cd backend && /workspace/.venv/bin/python smoke_test.py`
  (note: it re-fetches ShareTechnote/3GPP pages over the network to exercise RAG).
- No dedicated linter is configured in this repo.
