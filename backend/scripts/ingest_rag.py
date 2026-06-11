"""Build ShareTechnote / 3GPP RAG chunk store.

Run from repo root:
    python backend/scripts/ingest_rag.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.ingest import SEED_URLS, ingest_urls
from rag.store import save_chunks


def main() -> None:
    print("Ingesting reference pages...")
    chunks = ingest_urls(SEED_URLS, follow_index=True)
    path = save_chunks(chunks)
    print(f"Saved {len(chunks)} chunks -> {path}")


if __name__ == "__main__":
    main()
