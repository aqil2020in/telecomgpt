"""Startup RAG reindex — run on deploy / app boot."""

from __future__ import annotations

import logging
import os
import threading

_log = logging.getLogger("telecomgpt.startup")
_reindex_lock = threading.Lock()
_reindex_done = False


def reindex_rag_chunks(*, ingest: bool = False) -> dict:
    """Rebuild chunk store (optional) and index into vector memory."""
    from pathlib import Path

    backend = Path(__file__).resolve().parent.parent
    result: dict = {"ingested": False, "chunks": 0, "vector_indexed": 0}

    if ingest:
        try:
            from rag.ingest import SEED_URLS, ingest_urls
            from rag.store import save_chunks

            chunks = ingest_urls(SEED_URLS, follow_index=True)
            save_chunks(chunks)
            result["ingested"] = True
            result["chunks"] = len(chunks)
            _log.info("RAG ingest: %s chunks", len(chunks))
        except Exception as e:
            result["ingest_error"] = str(e)[:300]
            _log.warning("RAG ingest failed: %s", e)

    try:
        from memory.runtime_config import vector_enabled

        if not vector_enabled():
            result["vector_skipped"] = True
            return result
        from rag.store import load_chunks
        from memory.vector_store import VectorMemory

        chunks = load_chunks()
        result["chunks"] = len(chunks)
        if chunks:
            count = VectorMemory().ingest_rag_chunks(chunks)
            result["vector_indexed"] = count
            _log.info("Vector ingest: %s chunks", count)
    except Exception as e:
        result["vector_error"] = str(e)[:300]
        _log.warning("Vector ingest failed: %s", e)

    return result


def run_startup_reindex_background(*, ingest_on_boot: bool | None = None) -> None:
    """Fire-and-forget reindex so /ask is not blocked."""
    global _reindex_done

    if os.environ.get("TELECOMGPT_AUTO_REINDEX", "1") != "1":
        return

    with _reindex_lock:
        if _reindex_done:
            return
        _reindex_done = True

    do_ingest = ingest_on_boot
    if do_ingest is None:
        do_ingest = os.environ.get("TELECOMGPT_INGEST_ON_BOOT", "0") == "1"

    def _job() -> None:
        reindex_rag_chunks(ingest=do_ingest)

    threading.Thread(target=_job, name="rag-reindex", daemon=True).start()
