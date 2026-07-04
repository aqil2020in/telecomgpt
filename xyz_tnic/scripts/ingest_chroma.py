#!/usr/bin/env python3
"""Ingest telecom RCA knowledge documents into ChromaDB."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("TNIC_ENABLE_CHROMA", "1")
os.environ.setdefault("APP_ENV", "development")

from tnic.logging_config import setup_logging, get_logger  # noqa: E402
from tnic.rag.retriever import get_rag_store  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest TNIC knowledge base into ChromaDB")
    parser.add_argument("--query", default="handover failure", help="Test search query after ingest")
    parser.add_argument("--k", type=int, default=3, help="Number of search results to print")
    args = parser.parse_args()

    setup_logging()
    log = get_logger(__name__)
    store = get_rag_store()
    count = store.load_seed_documents()
    log.info("Ingested %d documents into RAG store", count)
    hits = store.search(args.query, k=args.k)
    for i, hit in enumerate(hits, 1):
        print(f"{i}. [{hit.get('category')}] {hit.get('title')}")
        print(f"   {hit.get('text', '')[:160]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
