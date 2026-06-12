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

import os
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
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


class ProfileUpdate(BaseModel):
    bands: list[str] = []
    devices: list[str] = []
    notes: str = ""


app = FastAPI(title="TelecomGPT", version="0.5.0")
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


@app.on_event("startup")
def _startup_reindex() -> None:
    from telecom_ai.startup_tasks import run_startup_reindex_background

    run_startup_reindex_background()


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
            "GET /api/reports/{filename}": "Download generated .pptx or .xlsx",
            "POST /api/upload": "Upload CSV/log for session-scoped analysis",
            "GET /api/profile/{session_id}": "Get user profile (bands, devices)",
            "POST /api/profile/{session_id}": "Update user profile",
            "POST /api/eval/smoke": "Run KB smoke-test eval",
            "GET /api/agents/taxonomy": "Task / retrieval / autonomous agent map",
            "GET /api/memory/{session_id}": "Memory snapshot (short + long-term)",
            "POST /api/memory/{session_id}/refresh": "Compact session → long-term memory",
            "GET /api/guardrails": "Guardrails & compliance policy",
            "GET /api/integrations": "External API / serverless integrations",
            "GET /api/monitoring/runs": "Recent orchestrator run summaries",
            "GET /api/engines": "Hybrid engine status (LangGraph + CrewAI + AutoGen)",
            "GET /api/jobs/{job_id}": "Poll async /ask job status and result",
        },
        "analytics_ui": "streamlit run analytics/app.py",
    }


def _is_slow_query(query: str) -> bool:
    ql = query.lower()
    slow_kw = (
        "chart", "ppt", "powerpoint", "csv", "upload", "compare", "eval", "deploy",
        "kaggle", "dashboard", "map", "excel", "report", "predict", "log", "smoke",
    )
    return any(k in ql for k in slow_kw)


def _format_ask_result(result: dict, *, trace: bool) -> dict:
    if trace:
        return result
    return {
        "answer": result.get("answer") or "",
        "session_id": result.get("session_id"),
        "artifacts": result.get("artifacts") or [],
        "sources": result.get("sources") or [],
        "confidence": result.get("confidence"),
        "plan": result.get("plan"),
        "workflow_tasks": result.get("workflow_tasks") or [],
        "guardrail_issues": result.get("guardrail_issues") or [],
        "mode": result.get("mode"),
    }


@app.post("/ask")
def ask(q: Query):
    history = [{"role": m.role, "content": m.content} for m in q.history]
    if _should_use_async_ask(q.query, q.trace):
        from telecom_ai.job_store import job_store

        job_id = job_store.create(q.query, trace=q.trace)

        def _run() -> dict:
            return agent.run_with_trace(q.query, history=history, session_id=q.session_id)

        job_store.run_in_background(job_id, _run)
        return {
            "async": True,
            "job_id": job_id,
            "status": "queued",
            "message": "Long task queued — poll GET /api/jobs/{job_id} for results.",
        }

    if _should_use_fast_ask(q.query, q.trace):
        result = agent.run_fast(q.query, history=history, session_id=q.session_id)
    else:
        result = agent.run_with_trace(q.query, history=history, session_id=q.session_id)
    return _format_ask_result(result, trace=q.trace)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    from fastapi import HTTPException

    from telecom_ai.job_store import job_store

    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    payload: dict = {
        "job_id": job.id,
        "status": job.status,
        "query": job.query,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
    if job.status == "completed" and job.result:
        payload.update(_format_ask_result(job.result, trace=job.trace))
    if job.status == "failed":
        payload["error"] = job.error or "Job failed"
    return payload


def _should_use_async_ask(query: str, trace: bool) -> bool:
    if trace:
        return False
    if os.environ.get("TELECOMGPT_ASYNC_ASK", "1") != "1":
        return False
    return _is_slow_query(query)


def _should_use_fast_ask(query: str, trace: bool) -> bool:
    """Use fast RAG+LLM path for typical Q&A (avoids Render timeout)."""
    if trace:
        return False
    if os.environ.get("TELECOMGPT_FAST_ASK", "1") != "1":
        return False
    if _is_slow_query(query):
        return False
    return len(query.split()) <= 24


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
    if not path.exists():
        return {"error": "Report not found"}
    suffix = path.suffix.lower()
    if suffix == ".pptx":
        media = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    elif suffix == ".xlsx":
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        return {"error": "Unsupported report type"}
    return FileResponse(path, media_type=media, filename=filename)


@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form("default"),
):
    uploads_dir = Path(__file__).resolve().parent / "data" / "uploads" / session_id
    uploads_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload").name
    dest = uploads_dir / safe_name
    content = await file.read()
    dest.write_bytes(content)
    return {
        "ok": True,
        "filename": safe_name,
        "path": str(dest),
        "session_id": session_id,
        "size_bytes": len(content),
    }


@app.get("/api/profile/{session_id}")
def get_profile(session_id: str):
    from memory.user_profile import UserProfile

    return UserProfile(session_id).load()


@app.post("/api/profile/{session_id}")
def update_profile(session_id: str, body: ProfileUpdate):
    from memory.user_profile import UserProfile

    profile = UserProfile(session_id)
    data = profile.load()
    if body.bands:
        data["bands"] = body.bands
    if body.devices:
        data["devices"] = body.devices
    if body.notes:
        data["notes"] = body.notes
    profile.save(data)
    return data


@app.post("/api/eval/smoke")
def eval_smoke():
    from telecom_ai.agents.extended import run_eval_agent

    return run_eval_agent(agent.db)


@app.get("/api/agents/taxonomy")
def agents_taxonomy():
    from telecom_ai.agents.taxonomy import taxonomy_summary

    return taxonomy_summary()


@app.get("/api/memory/{session_id}")
def memory_snapshot(session_id: str):
    from memory.memory_manager import MemoryManager

    mgr = MemoryManager(session_id)
    query = "telecom bands devices 5G"
    return {
        "session_id": session_id,
        "short_term_turns": len(mgr.session.load()),
        "profile": mgr.profile.load(),
        "semantic": mgr.retrieve_semantic(query, k=5),
        "episodic": mgr.retrieve_episodic(query, k=5),
        "procedural": mgr.retrieve_procedural(query, k=5),
        "provider": __import__("os").environ.get("TELECOMGPT_MEMORY", "chroma"),
    }


@app.post("/api/memory/{session_id}/refresh")
def memory_refresh(session_id: str):
    from memory.adapters import get_memory_adapter

    adapter = get_memory_adapter()
    return adapter.refresh(user_id=session_id)


@app.get("/api/guardrails")
def guardrails_info():
    from telecom_ai.guardrails import compliance_notice

    return {
        "policy": compliance_notice(),
        "features": [
            "input_policy_filter",
            "output_content_filter",
            "pii_redaction_imsi_imei",
            "tool_allowlist_by_agent_category",
            "verifier_kb_crosscheck",
            "confidence_clarification_gate",
        ],
    }


@app.get("/api/integrations")
def integrations_list():
    from telecom_ai.integrations import list_integrations

    return {"integrations": list_integrations()}


@app.get("/api/monitoring/runs")
def monitoring_runs(limit: int = 20):
    from telecom_ai.monitoring import recent_runs

    return {"runs": recent_runs(limit=min(limit, 50))}


@app.get("/api/engines")
def engines_status():
    from telecom_ai.engines import engine_status

    return engine_status()


@app.get("/api/rag/status")
def rag_status():
    import os

    from rag.store import load_chunks

    chunks = load_chunks()
    return {
        "chunks": len(chunks),
        "live_fetch": os.environ.get("TELECOMGPT_LIVE_FETCH", "1") == "1",
        "web_search": bool(os.environ.get("TAVILY_API_KEY")),
        "auto_reindex": os.environ.get("TELECOMGPT_AUTO_REINDEX", "1") == "1",
    }


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

    from telecom_ai.engines import engine_status
    from telecom_ai.reasoning import _ollama_reachable

    return {
        "status": "ok",
        "devices": len(agent.db.devices),
        "llm": {
            "openai_configured": bool(os.environ.get("OPENAI_API_KEY")),
            "ollama_reachable": _ollama_reachable(),
            "mode": os.environ.get("TELECOMGPT_MODE", "orchestrator"),
        },
        "engines": engine_status(),
    }


@app.get("/api/devices")
def devices():
    return agent.db.list_devices()


@app.get("/api/bands")
def bands():
    return agent.db.list_bands()
