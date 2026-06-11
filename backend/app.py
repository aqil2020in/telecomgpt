"""TelecomGPT backend API (FastAPI).

Run:
    cd backend
    uvicorn app:app --host 0.0.0.0 --port 8000

Endpoints:
    POST /ask           — {"query": "..."} -> {"answer": "..."}
    GET  /api/health    — liveness probe
    GET  /api/devices   — device capability summaries
    GET  /api/bands     — NR + LTE band plans
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from telecom_ai.core import TelecomAI

try:
    from analytics.routes import router as analytics_router
except ImportError:
    analytics_router = None


class ChatMessage(BaseModel):
    role: str
    content: str


class Query(BaseModel):
    query: str
    trace: bool = False
    history: list[ChatMessage] = []


app = FastAPI(title="TelecomGPT", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = Path("backend/data/telecom_master_db.json")
if not DB_PATH.exists():
    # Resolve relative to this file when uvicorn runs from a different cwd.
    DB_PATH = Path(__file__).resolve().parent / "data" / "telecom_master_db.json"

agent = TelecomAI(db_path=str(DB_PATH))

if analytics_router is not None:
    app.include_router(analytics_router)


@app.get("/")
def root():
    return {
        "name": "TelecomGPT API",
        "docs": "/docs",
        "ui": "https://telecomgpt.vercel.app",
        "endpoints": {
            "POST /ask": '{"query": "..."} -> {"answer": "..."}',
            "GET /api/health": "liveness probe",
            "GET /api/devices": "device summaries",
            "GET /api/bands": "NR + LTE band plans",
            "POST /api/analytics/csv/summary": "CSV upload -> summary",
            "POST /api/analytics/csv/chart": "CSV upload -> Plotly chart JSON",
            "POST /api/analytics/logs/analyze": "Log upload -> level counts + errors",
        },
        "analytics_ui": "streamlit run analytics/app.py",
    }


@app.post("/ask")
def ask(q: Query):
    history = [{"role": m.role, "content": m.content} for m in q.history]
    if q.trace:
        return agent.run_with_trace(q.query, history=history)
    return {"answer": agent.run(q.query, history=history)}


@app.post("/api/rag/reindex")
def rag_reindex():
    """Rebuild RAG chunk store from ShareTechnote seed URLs (admin/dev)."""
    from rag.ingest import SEED_URLS, ingest_urls
    from rag.store import save_chunks

    chunks = ingest_urls(SEED_URLS, follow_index=True)
    path = save_chunks(chunks)
    return {"status": "ok", "chunks": len(chunks), "path": str(path)}


@app.get("/api/health")
def health():
    return {"status": "ok", "devices": len(agent.db.devices)}


@app.get("/api/devices")
def devices():
    return agent.db.list_devices()


@app.get("/api/bands")
def bands():
    return agent.db.list_bands()
