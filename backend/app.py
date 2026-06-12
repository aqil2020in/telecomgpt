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
from fastapi.responses import FileResponse
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
    session_id: str | None = None


class PptRequest(BaseModel):
    topic: str
    content: str
    session_id: str = "default"


app = FastAPI(title="TelecomGPT", version="0.4.0")
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
            "GET /api/analytics/kaggle/charts": "Kaggle CSV auto-charts (query, path)",
            "POST /api/analytics/logs/analyze": "Log upload -> level counts + errors",
            "GET /api/tools": "List agent tools",
            "POST /api/ppt/generate": "Generate PowerPoint report",
            "GET /api/reports/{filename}": "Download generated .pptx",
        },
        "analytics_ui": "streamlit run analytics/app.py",
    }


@app.post("/ask")
def ask(q: Query):
    history = [{"role": m.role, "content": m.content} for m in q.history]
    result = agent.run_with_trace(q.query, history=history, session_id=q.session_id)
    if q.trace:
        return result
    return {
        "answer": result.get("answer") or "",
        "session_id": result.get("session_id"),
        "artifacts": result.get("artifacts") or [],
    }


@app.get("/api/tools")
def list_tools():
    return {"tools": agent.list_tools()}


@app.post("/api/ppt/generate")
def generate_ppt(req: PptRequest):
    from ppt.generator import generate_presentation

    return generate_presentation(
        topic=req.topic,
        content=req.content,
        session_id=req.session_id,
    )


@app.get("/api/reports/{filename}")
def download_report(filename: str):
    reports_dir = Path(__file__).resolve().parent / "data" / "reports"
    path = reports_dir / filename
    if not path.exists() or path.suffix.lower() != ".pptx":
        return {"error": "Report not found"}
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=filename,
    )


@app.post("/api/memory/ingest-rag")
def ingest_rag_to_memory():
    """Index RAG chunks into vector memory for hybrid retrieval."""
    from memory.vector_store import VectorMemory
    from rag.store import load_chunks

    chunks = load_chunks()
    count = VectorMemory().ingest_rag_chunks(chunks)
    return {"status": "ok", "indexed": count}


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
    import os

    from telecom_ai.reasoning import _ollama_reachable

    return {
        "status": "ok",
        "devices": len(agent.db.devices),
        "llm": {
            "openai_configured": bool(os.environ.get("OPENAI_API_KEY")),
            "ollama_reachable": _ollama_reachable(),
            "mode": os.environ.get("TELECOMGPT_MODE", "orchestrator"),
        },
    }


@app.get("/api/devices")
def devices():
    return agent.db.list_devices()


@app.get("/api/bands")
def bands():
    return agent.db.list_bands()
