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


class Query(BaseModel):
    query: str


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


@app.post("/ask")
def ask(q: Query):
    answer = agent.run(q.query)
    return {"answer": answer}


@app.get("/api/health")
def health():
    return {"status": "ok", "devices": len(agent.db.devices)}


@app.get("/api/devices")
def devices():
    return agent.db.list_devices()


@app.get("/api/bands")
def bands():
    return agent.db.list_bands()
