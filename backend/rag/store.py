"""Persist and load RAG chunk store."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_STORE = Path(__file__).resolve().parent.parent / "data" / "rag" / "chunks.json"


def save_chunks(chunks: list[dict], path: Path | None = None) -> Path:
    target = path or DEFAULT_STORE
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "count": len(chunks), "chunks": chunks}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_chunks(path: Path | None = None) -> list[dict]:
    target = path or DEFAULT_STORE
    if not target.exists():
        return []
    data = json.loads(target.read_text(encoding="utf-8"))
    return data.get("chunks", [])
